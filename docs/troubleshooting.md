# Troubleshooting

Common issues and their solutions. If your problem is not listed here,
[open an issue](https://github.com/NetApp/pace/issues/new?template=bug_report.yml)
or start a [discussion](https://github.com/NetApp/pace/discussions).

---

## Connection Errors

### "Connection refused" or timeout when running a script

The machine cannot reach the ONTAP cluster management LIF.

- Verify `ONTAP_HOST` (or `ontap_hostname` / `ontap_host`) is correct.
- Confirm HTTPS (port 443) is open between your machine and the cluster:
  ```bash
  curl -kI https://<ONTAP_HOST>/api/cluster
  ```
- If you are behind a proxy or VPN, ensure the cluster IP is routable.

### DNS resolution failure

If you use a hostname instead of an IP, make sure it resolves:

```bash
nslookup <ONTAP_HOST>
```

---

## Authentication Failures

### HTTP 401 - Unauthorized

- Double-check `ONTAP_USER` and `ONTAP_PASS` (or the Ansible/Terraform equivalents).
- Ensure the user account is not locked (`security login show -vserver <svm>`).
- Verify the user has REST API access (`security login role show`).

### HTTP 403 - Forbidden

The credentials are valid but the user lacks the required RBAC permissions
for the endpoint being called. Check the ONTAP documentation for the
minimum role needed.

---

## SSL / TLS Errors

### "SSL: CERTIFICATE_VERIFY_FAILED"

All examples default to `verify_ssl=false` / `validate_certs=false` to
support self-signed certificates. If you see this error, either:

1. Set the verify flag to `false` (already the default), or
2. Export your cluster's CA certificate and point to it:
   ```bash
   export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
   ```

### InsecureRequestWarning flood

The `ontap_client.py` module suppresses urllib3 insecure-request warnings.
If you still see them, ensure you are importing `ontap_client` before making
any `requests` calls.

---

## Python Script Issues

### `ModuleNotFoundError: No module named 'ontap_client'`

Scripts must be run from their product directory so that the sibling client
module (`ontap_client.py`) is on the Python path:

```bash
cd python/ontap
python cluster_info.py
```

### `ONTAP_HOST environment variable is required`

Set the required environment variables before running any script:

```bash
export ONTAP_HOST=<your-cluster-ip>
export ONTAP_PASS=<your-password>
```

Or use an env file:

```bash
set -a && source cluster.env && set +a
```

### `ModuleNotFoundError: No module named 'requests'`

Install dependencies first:

```bash
pip install -r python/ontap/requirements.txt
```

---

## Ansible Issues

### `ERROR! the role 'netapp.ontap.*' was not found`

Install the NetApp ONTAP Ansible collection:

```bash
ansible-galaxy collection install -r ansible/ontap/requirements.yml
```

### Vault decrypt error

If `group_vars/ontap.yml` is encrypted with Ansible Vault, pass the
vault password:

```bash
cd ansible/ontap
ansible-playbook -i inventory/hosts.yml cluster_info.yml --ask-vault-pass
```

### Inventory host mismatch

Ensure `ansible/ontap/inventory/hosts.yml` contains the correct hostname or IP
for your cluster. The default `10.0.0.1` is a placeholder.

---

## Terraform Issues

### Provider initialization failure

Run `terraform init` before `terraform apply`:

```bash
cd terraform/ontap/cluster-info
terraform init
```

If you see "Failed to query available provider packages", check your
network connectivity and proxy settings.

### "No value for required variable"

Copy the example tfvars file and fill in your values:

```bash
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
```

### State file conflicts

If you are sharing a Terraform module across environments, use a remote
backend or separate workspaces to avoid state collisions.

---

## NFS Provisioning

### Volume already exists

The Python `nfs_provision.py` script is not idempotent - running it twice
with the same volume name will fail. Either:

- Choose a different volume name, or
- Add an existence check before creating (see `python/ontap/README.md` →
  "Adapting for Your Environment").

### Aggregate not found

The `--aggregate` (or `aggregate_name`) value must match an existing
aggregate on your cluster. List aggregates with:

```bash
curl -ku admin https://<ONTAP_HOST>/api/storage/aggregates?fields=name
```

### `client_match` too permissive

The default `0.0.0.0/0` allows all clients. Restrict it to your actual
client subnet in production:

```bash
python nfs_provision.py --client-match 10.0.0.0/8
```

---

## Pre-commit and CI

### TruffleHog false positive

TruffleHog only flags **verified** secrets (credentials that actually
authenticate against a live service). If you believe a finding is a false
positive, you can add the path to a `.trufflehogignore` file at the repo
root.

### Commitlint rejects your message

Commit messages must follow
[Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>
```

Valid types: `build`, `chore`, `ci`, `doc`, `feat`, `fix`, `perf`,
`refactor`, `revert`, `style`, `test`.

### Ruff lint errors

Run Ruff locally to see and auto-fix issues:

```bash
ruff check python/ --fix
ruff format python/
```

Or use the Makefile:

```bash
make lint
```

---

## Docker

### Build fails on ARM / Apple Silicon

The Dockerfile defaults to `linux/amd64` for the Terraform binary. On
ARM-based machines, either:

- Use `docker build --platform linux/amd64 .` (with Rosetta on macOS), or
- Change the `TERRAFORM_VERSION` URL in the Dockerfile to use the
  `linux_arm64` variant.
