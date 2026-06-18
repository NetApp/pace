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
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

const (
	defaultTimeout = 30 * time.Second
	clientAppHdr   = "pace-example"
	maxJobWait     = 10 * time.Minute
	maxRespBytes   = 32 << 20 // 32 MiB safety cap on response body size

	// PathStorageVolumes is the ONTAP REST API path for storage volume operations.
	PathStorageVolumes = "/storage/volumes"

	// KeySVMName is the query parameter key for filtering resources by SVM name.
	KeySVMName = "svm.name"
)

// OntapApiError is returned when the ONTAP REST API responds with a non-2xx status.
type OntapApiError struct {
	StatusCode int
	Detail     interface{}
}

func (e *OntapApiError) Error() string {
	return fmt.Sprintf("HTTP %d: %v", e.StatusCode, e.Detail)
}

// ErrorCode extracts the ONTAP API error code string from the parsed response body.
// Returns an empty string if the code field is absent or unparseable.
// Example ONTAP error body: {"error": {"code": "917927", "message": "entry already exists"}}
func (e *OntapApiError) ErrorCode() string {
	m, ok := e.Detail.(map[string]interface{})
	if !ok {
		return ""
	}
	errMap, ok := m["error"].(map[string]interface{})
	if !ok {
		return ""
	}
	code, _ := errMap["code"].(string)
	return code
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
// Returns an error if a required variable is unset so callers can handle it
// without os.Exit side-effects (important for testability).
func FromEnv() (*Client, error) {
	host := os.Getenv("ONTAP_HOST")
	if host == "" {
		return nil, fmt.Errorf("ONTAP_HOST environment variable is required")
	}
	password := os.Getenv("ONTAP_PASS")
	if password == "" {
		return nil, fmt.Errorf("ONTAP_PASS environment variable is required")
	}
	user := os.Getenv("ONTAP_USER")
	if user == "" {
		user = "admin"
	}
	return New(host, user, password, false), nil
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
func (c *Client) do(ctx context.Context, method, rawURL string, body interface{}) (map[string]interface{}, error) {
	var bodyReader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("marshal request body: %w", err)
		}
		bodyReader = bytes.NewReader(b)
	}

	req, err := http.NewRequestWithContext(ctx, method, rawURL, bodyReader)
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

	limited := io.LimitReader(resp.Body, maxRespBytes+1)
	respBytes, err := io.ReadAll(limited)
	if err != nil {
		return nil, fmt.Errorf("read response body: %w", err)
	}
	if int64(len(respBytes)) > maxRespBytes {
		return nil, fmt.Errorf("response body exceeds 32 MiB — add max_records to reduce response size")
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
func (c *Client) Get(ctx context.Context, path string, params map[string]string) (map[string]interface{}, error) {
	return c.do(ctx, http.MethodGet, c.buildURL(path, params), nil)
}

// Post sends a POST request with a JSON body and optional query params.
func (c *Client) Post(ctx context.Context, path string, params map[string]string, body interface{}) (map[string]interface{}, error) {
	return c.do(ctx, http.MethodPost, c.buildURL(path, params), body)
}

// Patch sends a PATCH request with a JSON body and optional query params.
func (c *Client) Patch(ctx context.Context, path string, params map[string]string, body interface{}) (map[string]interface{}, error) {
	return c.do(ctx, http.MethodPatch, c.buildURL(path, params), body)
}

// Delete sends a DELETE request with optional query params.
func (c *Client) Delete(ctx context.Context, path string, params map[string]string) (map[string]interface{}, error) {
	return c.do(ctx, http.MethodDelete, c.buildURL(path, params), nil)
}

// PollJob polls /cluster/jobs/{uuid} until the job reaches a terminal state.
// Returns an error if the job ends in any state other than "success".
func (c *Client) PollJob(ctx context.Context, jobUUID string, interval time.Duration) (map[string]interface{}, error) {
	if interval <= 0 {
		interval = 10 * time.Second
	}
	deadline := time.Now().Add(maxJobWait)
	for {
		if time.Now().After(deadline) {
			return nil, fmt.Errorf("poll job %s: timed out after %s", jobUUID, maxJobWait)
		}
		result, err := c.Get(ctx, fmt.Sprintf("/cluster/jobs/%s", jobUUID),
			map[string]string{"fields": "state,message,error,code"})
		if err != nil {
			return nil, fmt.Errorf("poll job %s: %w", jobUUID, err)
		}
		state, _ := result["state"].(string)
		log.Printf("  job %s — state=%s", jobUUID, state)
		switch state {
		case "running", "queued", "paused":
			time.Sleep(interval)
		case "success":
			return result, nil
		default:
			msg, _ := result["message"].(string)
			return nil, fmt.Errorf("job %s ended with state=%s: %s", jobUUID, state, msg)
		}
	}
}

// WaitSnapmirrored polls a SnapMirror relationship until state == "snapmirrored".
// Defaults: interval=15s, maxWait=30m when zero or negative values are provided.
func (c *Client) WaitSnapmirrored(ctx context.Context, relUUID string, interval, maxWait time.Duration) (map[string]interface{}, error) {
	if interval <= 0 {
		interval = 15 * time.Second
	}
	if maxWait <= 0 {
		maxWait = 30 * time.Minute
	}
	deadline := time.Now().Add(maxWait)
	for {
		if time.Now().After(deadline) {
			return nil, fmt.Errorf("timed out waiting for relationship %s to reach snapmirrored", relUUID)
		}
		result, err := c.Get(ctx, fmt.Sprintf("/snapmirror/relationships/%s", relUUID),
			map[string]string{"fields": "state,lag_time,healthy"})
		if err != nil {
			return nil, fmt.Errorf("poll relationship %s: %w", relUUID, err)
		}
		state, _ := result["state"].(string)
		log.Printf("  relationship %s — state=%s", relUUID, state)
		if state == "snapmirrored" {
			return result, nil
		}
		time.Sleep(interval)
	}
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

// PollJobTolerant is like PollJob but retries on transient network errors.
// Use when the management stack may restart during the operation (e.g. POST /cluster).
// HTTP-level API errors (4xx/5xx) are returned immediately without retrying.
func (c *Client) PollJobTolerant(ctx context.Context, jobUUID string, interval time.Duration) (map[string]interface{}, error) {
	if interval <= 0 {
		interval = 10 * time.Second
	}
	deadline := time.Now().Add(maxJobWait)
	jobPath := fmt.Sprintf("/cluster/jobs/%s", jobUUID)
	for {
		if time.Now().After(deadline) {
			return nil, fmt.Errorf("poll job %s: timed out after %s", jobUUID, maxJobWait)
		}
		result, err := c.Get(ctx, jobPath, map[string]string{"fields": "state,message,error,code"})
		if err != nil {
			var apiErr *OntapApiError
			if errors.As(err, &apiErr) {
				// HTTP-level error — not a transient reboot; return immediately.
				return nil, fmt.Errorf("poll job %s: %w", jobUUID, err)
			}
			// Network error — management stack may be restarting; retry.
			log.Printf("  job %s — network error, retrying in %s — %v", jobUUID, interval, err)
			time.Sleep(interval)
			continue
		}
		state, _ := result["state"].(string)
		log.Printf("  job %s — state=%s", jobUUID, state)
		switch state {
		case "running", "queued", "paused":
			time.Sleep(interval)
		case "success":
			return result, nil
		default:
			msg, _ := result["message"].(string)
			return nil, fmt.Errorf("job %s ended with state=%s: %s", jobUUID, state, msg)
		}
	}
}

// MustEnv reads an environment variable and calls log.Fatal if it is not set or empty.
func MustEnv(key string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	log.Fatalf("'%s' is required — set it in go/.env or as an environment variable", key)
	return ""
}

// EnvOrDefault reads an environment variable, returning defaultVal if unset or empty.
func EnvOrDefault(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}

// DieOnErr calls log.Fatal if err is non-nil. For use in main packages only.
func DieOnErr(op string, err error) {
	if err != nil {
		log.Fatalf("%s: %v", op, err)
	}
}

// LoadDotEnv reads a .env file from the current directory and sets each KEY=VALUE
// pair as an environment variable (only if not already set). The file is gitignored —
// safe to store credentials there for local testing.
func LoadDotEnv() {
	data, err := os.ReadFile(".env")
	if err != nil {
		return
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		k, v, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		if os.Getenv(strings.TrimSpace(k)) == "" {
			_ = os.Setenv(strings.TrimSpace(k), strings.TrimSpace(v))
		}
	}
}
