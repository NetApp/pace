// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.

// Package ontapclient provides a lightweight ONTAP REST API client.
//
// Usage:
//
//	client := ontapclient.New("10.x.x.x", "admin", "secret", false)
//	defer client.Close()
//	cluster, err := client.Get("/cluster", map[string]string{"fields": "name,version"})
package ontapclient

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"time"
)

const (
	defaultTimeout = 30 * time.Second
	clientAppHdr   = "pace-example"
	maxJobWait     = 10 * time.Minute
)

// OntapApiError is returned when the ONTAP REST API responds with a non-2xx status.
type OntapApiError struct {
	StatusCode int
	Detail     interface{}
}

func (e *OntapApiError) Error() string {
	return fmt.Sprintf("HTTP %d: %v", e.StatusCode, e.Detail)
}

// Client is a thin HTTP client for the ONTAP REST API.
type Client struct {
	baseURL    string
	username   string
	password   string
	httpClient *http.Client
}

// New creates a new Client.
// Set verifySSL=false to allow self-signed certificates (common in lab environments).
func New(host, username, password string, verifySSL bool) *Client {
	transport := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: !verifySSL}, // #nosec G402 — intentional for lab certs
	}
	return &Client{
		baseURL:  fmt.Sprintf("https://%s/api", host),
		username: username,
		password: password,
		httpClient: &http.Client{
			Timeout:   defaultTimeout,
			Transport: transport,
		},
	}
}

// FromEnv creates a Client from standard ONTAP_* environment variables.
// Required: ONTAP_HOST, ONTAP_PASS. Optional: ONTAP_USER (default "admin").
func FromEnv() *Client {
	host := os.Getenv("ONTAP_HOST")
	if host == "" {
		log.Fatal("ONTAP_HOST environment variable is required")
	}
	password := os.Getenv("ONTAP_PASS")
	if password == "" {
		log.Fatal("ONTAP_PASS environment variable is required")
	}
	user := os.Getenv("ONTAP_USER")
	if user == "" {
		user = "admin"
	}
	return New(host, user, password, false)
}

// Close is a no-op provided for symmetry with connection-pooling patterns.
func (c *Client) Close() {
	c.httpClient.CloseIdleConnections()
}

// buildURL constructs a full API URL with query parameters.
func (c *Client) buildURL(path string, params map[string]string) string {
	u := c.baseURL + path
	if len(params) == 0 {
		return u
	}
	q := url.Values{}
	for k, v := range params {
		q.Set(k, v)
	}
	return u + "?" + q.Encode()
}

// do executes an HTTP request and decodes the JSON response body.
func (c *Client) do(method, rawURL string, body interface{}) (map[string]interface{}, error) {
	var bodyReader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("marshal request body: %w", err)
		}
		bodyReader = bytes.NewReader(b)
	}

	req, err := http.NewRequest(method, rawURL, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.SetBasicAuth(c.username, c.password)
	req.Header.Set("Accept", "application/hal+json")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Dot-Client-App", clientAppHdr)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("execute request: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	respBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response body: %w", err)
	}

	var result map[string]interface{}
	if len(respBytes) > 0 {
		if err := json.Unmarshal(respBytes, &result); err != nil {
			result = map[string]interface{}{"_raw": string(respBytes)}
		}
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return result, &OntapApiError{StatusCode: resp.StatusCode, Detail: result}
	}
	return result, nil
}

// Get sends a GET request to the given API path with optional query params.
func (c *Client) Get(path string, params map[string]string) (map[string]interface{}, error) {
	return c.do(http.MethodGet, c.buildURL(path, params), nil)
}

// Post sends a POST request with a JSON body.
func (c *Client) Post(path string, body interface{}) (map[string]interface{}, error) {
	return c.do(http.MethodPost, c.baseURL+path, body)
}

// Patch sends a PATCH request with a JSON body.
func (c *Client) Patch(path string, body interface{}) (map[string]interface{}, error) {
	return c.do(http.MethodPatch, c.baseURL+path, body)
}

// Delete sends a DELETE request.
func (c *Client) Delete(path string) (map[string]interface{}, error) {
	return c.do(http.MethodDelete, c.baseURL+path, nil)
}

// PollJob polls /cluster/jobs/{uuid} until the job reaches a terminal state.
// Returns an error if the job ends in any state other than "success".
func (c *Client) PollJob(jobUUID string, intervalSecs int) (map[string]interface{}, error) {
	if intervalSecs <= 0 {
		intervalSecs = 10
	}
	deadline := time.Now().Add(maxJobWait)
	for {
		if time.Now().After(deadline) {
			return nil, fmt.Errorf("poll job %s: timed out after %s", jobUUID, maxJobWait)
		}
		result, err := c.Get(fmt.Sprintf("/cluster/jobs/%s", jobUUID),
			map[string]string{"fields": "state,message,error,code"})
		if err != nil {
			return nil, fmt.Errorf("poll job %s: %w", jobUUID, err)
		}
		state, _ := result["state"].(string)
		log.Printf("  job %s — state=%s", jobUUID, state)
		switch state {
		case "running", "queued", "paused":
			time.Sleep(time.Duration(intervalSecs) * time.Second)
		case "success":
			return result, nil
		default:
			msg, _ := result["message"].(string)
			return nil, fmt.Errorf("job %s ended with state=%s: %s", jobUUID, state, msg)
		}
	}
}

// WaitSnapmirrored polls a SnapMirror relationship until state == "snapmirrored".
// maxWaitSecs defaults to 1800 if <= 0.
func (c *Client) WaitSnapmirrored(relUUID string, intervalSecs, maxWaitSecs int) (map[string]interface{}, error) {
	if intervalSecs <= 0 {
		intervalSecs = 15
	}
	if maxWaitSecs <= 0 {
		maxWaitSecs = 1800
	}
	elapsed := 0
	for elapsed < maxWaitSecs {
		result, err := c.Get(fmt.Sprintf("/snapmirror/relationships/%s", relUUID),
			map[string]string{"fields": "state,lag_time,healthy"})
		if err != nil {
			return nil, fmt.Errorf("poll relationship %s: %w", relUUID, err)
		}
		state, _ := result["state"].(string)
		log.Printf("  relationship %s — state=%s", relUUID, state)
		if state == "snapmirrored" {
			return result, nil
		}
		time.Sleep(time.Duration(intervalSecs) * time.Second)
		elapsed += intervalSecs
	}
	return nil, fmt.Errorf("timed out waiting for relationship %s to reach snapmirrored", relUUID)
}

// NestedStr safely extracts a nested string value from a map[string]interface{}.
// Keys are applied in order: NestedStr(m, "a", "b") => m["a"].(map)["b"].(string).
func NestedStr(m map[string]interface{}, keys ...string) string {
	cur := m
	for i, k := range keys {
		v, ok := cur[k]
		if !ok {
			return ""
		}
		if i == len(keys)-1 {
			s, _ := v.(string)
			return s
		}
		cur, ok = v.(map[string]interface{})
		if !ok {
			return ""
		}
	}
	return ""
}

// NestedFloat safely extracts a float64 from a nested map.
func NestedFloat(m map[string]interface{}, keys ...string) float64 {
	cur := m
	for i, k := range keys {
		v, ok := cur[k]
		if !ok {
			return 0
		}
		if i == len(keys)-1 {
			f, _ := v.(float64)
			return f
		}
		cur, ok = v.(map[string]interface{})
		if !ok {
			return 0
		}
	}
	return 0
}

// Records returns the "records" slice from a collection response.
func Records(resp map[string]interface{}) []map[string]interface{} {
	raw, ok := resp["records"]
	if !ok {
		return nil
	}
	slice, ok := raw.([]interface{})
	if !ok {
		return nil
	}
	out := make([]map[string]interface{}, 0, len(slice))
	for _, item := range slice {
		if m, ok := item.(map[string]interface{}); ok {
			out = append(out, m)
		}
	}
	return out
}

// NumRecords returns the num_records integer from a collection response.
func NumRecords(resp map[string]interface{}) int {
	v, ok := resp["num_records"]
	if !ok {
		return 0
	}
	f, ok := v.(float64)
	if !ok {
		return 0
	}
	return int(f)
}

// JobUUID extracts job.uuid from a response.
func JobUUID(resp map[string]interface{}) string {
	return NestedStr(resp, "job", "uuid")
}
