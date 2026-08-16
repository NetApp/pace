# netapp.console — Ansible Collection

Idempotent Ansible modules and ready-to-run playbooks for automating
[NetApp Console Local (NCL)](https://docs.netapp.com) REST APIs.

| | |
|---|---|
| **Galaxy** | [`netapp.console`](https://galaxy.ansible.com/ui/repo/published/netapp/console/) |
| **Playbook examples** | [github.com/NetApp/pace — ansible/console/local](https://github.com/NetApp/pace/tree/main/ansible/console/local) |

| | |
|---|---|
| **Collection** | `netapp.console` |
| **Version** | 1.0.0 |
| **ansible-core** | ≥ 2.15 |
| **Python** | ≥ 3.11 |
| **License** | Apache 2.0 |

---

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Repository Layout](#repository-layout)
5. [Configuration](#configuration)
6. [Idempotency Model](#idempotency-model)
7. [Modules Reference](#modules-reference)
8. [Playbooks Reference](#playbooks-reference)
9. [Writing Your Own Playbooks](#writing-your-own-playbooks)
10. [Secrets Management](#secrets-management)
11. [Ansible Automation Platform (AAP / AWX)](#ansible-automation-platform-aap--awx)
12. [Testing](#testing)

---

## Requirements

- **Python ≥ 3.11** linked against OpenSSL (not macOS LibreSSL).  
  On macOS, install via [pyenv](https://github.com/pyenv/pyenv) with OpenSSL:

  ```bash
  brew install openssl@3
  PYTHON_CONFIGURE_OPTS="--with-openssl=$(brew --prefix openssl@3)" \
      pyenv install 3.11.9 && pyenv global 3.11.9
  pip install ansible
  ```

- **ansible-core ≥ 2.15** — no extra pip packages required; all HTTP calls use
  the built-in `fetch_url` wrapper.

---

## Installation

### From Ansible Galaxy *(recommended)*

```bash
ansible-galaxy collection install netapp.console
```

Or, if you have cloned the PACE repo, use the bundled `requirements.yml`
(pins the minimum version and is the standard pattern for AAP / AWX projects):

```bash
ansible-galaxy collection install -r requirements.yml
```

### Playbook examples (PACE)

Ready-to-run playbooks and pre-filled variable templates live in the
[NetApp PACE repository](https://github.com/NetApp/pace/tree/main/ansible/console/local):

```bash
git clone https://github.com/NetApp/pace.git
cd pace/ansible/console/local
# edit vars/ncl.yml with your appliance details
ansible-playbook playbooks/site.yml --extra-vars "@vars/ncl.yml"
```

### From source (development / CI)

```bash
git clone https://github.com/NetApp/pace.git
cd pace/ansible/console/local
export ANSIBLE_COLLECTIONS_PATH="${PWD}"
```

The `ansible_collections/netapp/console` symlink inside the repo points back to
the root so Ansible resolves the collection without a Galaxy install.

---

## Quick Start

```bash
# 0. Get playbook examples from PACE
git clone https://github.com/NetApp/pace.git
cd pace/ansible/console/local

# 1. Install the collection from Galaxy
ansible-galaxy collection install netapp.console

# 2. Copy and fill in your appliance details
cp vars/ncl.yml vars/my_ncl.yml
vi vars/my_ncl.yml          # set ncl_console_url, ncl_admin_email, etc.

# 3. Full bootstrap (org → user → fleet → folder hierarchy)
ansible-playbook playbooks/site.yml --extra-vars "@vars/my_ncl.yml"

# 4. Provision a volume
ansible-playbook playbooks/storage_provisioning.yml \
    --extra-vars "@vars/my_ncl.yml" \
    --extra-vars "@vars/ncl_storage_provisioning.yml"

# 5. Configure Active Directory
ansible-playbook playbooks/active_directory.yml \
    --extra-vars "@vars/my_ncl.yml" \
    --extra-vars "@vars/ncl_active_directory.yml" \
    -e ncl_ad_action=create
```

---

## Repository Layout

The codebase is split across two public locations:

| Location | Contents |
|---|---|
| [Ansible Galaxy](https://galaxy.ansible.com/ui/repo/published/netapp/console/) | 25 modules (`plugins/`), collection metadata |
| [PACE — ansible/console/local](https://github.com/NetApp/pace/tree/main/ansible/console/local) | Runnable playbooks (`playbooks/`), variable templates (`vars/`) |

### PACE layout (`github.com/NetApp/pace/tree/main/ansible/console/local`)

```
ansible/console/local/
├── vars/
│   ├── ncl.yml                       # Shared appliance defaults (fill in once)
│   ├── ncl_active_directory.yml      # AD / LDAP federation variables
│   ├── ncl_capacity_policy.yml
│   ├── ncl_deregister_system.yml
│   ├── ncl_email_config.yml
│   ├── ncl_fleet.yml
│   ├── ncl_llm.yml
│   ├── ncl_performance_policy.yml
│   ├── ncl_protection_policy.yml
│   ├── ncl_register_and_onboard.yml
│   ├── ncl_register_onprem.yml
│   ├── ncl_org_users.yml
│   ├── ncl_security_policy.yml
│   ├── ncl_storage_class.yml
│   ├── ncl_storage_provisioning.yml
│   ├── ncl_volume_delete.yml
│   └── ncl_webhook.yml
└── playbooks/
    ├── site.yml                      # Full bootstrap entry point
    ├── active_directory.yml
    ├── capacity_policies.yml
    ├── deregister_system.yml
    ├── email_config.yml
    ├── fleet_management.yml
    ├── fleet_delete.yml
    ├── folder_management.yml
    ├── llm_config.yml
    ├── nested_folder_fleet.yml
    ├── performance_policies.yml
    ├── protection_policies.yml
    ├── register_and_onboard.yml
    ├── register_onprem_system.yml
│   ├── org_users.yml
│   ├── security_policies.yml
│   ├── service_account.yml
    ├── storage_classes.yml
    ├── storage_provisioning.yml
    ├── user_registration.yml
    ├── volumes_delete.yml
    └── webhooks.yml
```

> `plugins/`, `tests/`, `Makefile`, `galaxy.yml`, `.yamllint`, `.ansible-lint`,
> `changelogs/`, `meta/`, and `LICENSES/` are **not** published to PACE —
> they are part of the Galaxy collection artifact or internal dev tooling only.

> **`ansible.cfg` in PACE** is minimal — it sets `host_key_checking = False` and
> `stdout_callback = yaml` only. It intentionally does **not** set
> `collections_path`, so Ansible resolves `netapp.console` from the Galaxy
> default (`~/.ansible/collections`) after `ansible-galaxy collection install`.

---

## Configuration

### `vars/ncl.yml` — shared appliance settings

Fill in once; every playbook sources this file:

| Variable | Description | Default |
|---|---|---|
| `ncl_console_url` | HTTPS URL of the NCL appliance | — |
| `ncl_admin_email` | Admin email for initial login | — |
| `ncl_admin_password` | Admin password | — |
| `ncl_org_id` | Organisation UUID (auto-discovered if blank) | `""` |
| `ncl_access_token` | Bearer token (skip login if pre-set) | `""` |
| `ncl_validate_certs` | Validate TLS certificate | `false` |
| `ncl_timeout` | HTTP timeout (seconds) | `60` |

**Override at runtime:**

```bash
ansible-playbook playbooks/site.yml \
    --extra-vars "@vars/ncl.yml" \
    -e ncl_console_url=https://10.192.18.38 \
    -e ncl_validate_certs=false
```

**Environment variable shortcuts (CI / secrets managers):**

| Variable | Env var |
|---|---|
| `ncl_console_url` | `NCL_CONSOLE_URL` |
| `ncl_access_token` | `NCL_ACCESS_TOKEN` |
| `ncl_org_id` | `NCL_ORG_ID` |
| `ncl_validate_certs` | `NCL_VALIDATE_CERTS` |

---

## Idempotency Model

All modules implement the standard Ansible `state` contract — running the same
playbook multiple times is safe and produces no unintended side effects:

| `state` | Behaviour |
|---|---|
| `present` | Create the resource if it does not exist; update it if it exists but differs |
| `absent` | Delete the resource if it exists; no-op if already gone |
| `query` | Read-only — return current state, make no changes |

Modules that do not support all three states (e.g. `generate_oauth_token`,
`local_bootstrap`) document their supported values in the module's
`DOCUMENTATION` block — check with:

```bash
ansible-doc netapp.console.<module_name>
```

---

## Modules Reference

All modules share these common parameters:

| Parameter | Required | Description |
|---|---|---|
| `console_url` | yes | HTTPS base URL of the NCL appliance |
| `access_token` | yes | OAuth2 bearer token |
| `org_id` | most | Organisation UUID |
| `validate_certs` | no | TLS verification (default `false`) |
| `timeout` | no | Request timeout in seconds (default `60`) |

| Module | Description |
|---|---|
| `active_directory` | Manage Active Directory / LDAP federation (`query` / `present` / `absent`) |
| `add_new_systems` | Register on-premises ONTAP clusters in a Console org |
| `add_systems_to_fleet` | Attach ONTAP systems to a fleet |
| `capacity_policies` | Manage NCL capacity policies |
| `deregister_system` | Permanently remove an ONTAP system from the org |
| `email_config` | Configure outbound email (SMTP) settings |
| `folder_management` | Create / update / delete folder hierarchy |
| `generate_oauth_token` | Obtain an OAuth2 access token (ROPC grant) |
| `llm_config` | Configure LLM integration (provider, model, API key) |
| `local_agent_info` | Retrieve connector / agent details from the appliance |
| `local_bootstrap` | Bootstrap initial NCL appliance configuration |
| `local_organization_setup` | Create and configure organisations |
| `local_user_registration` | Register admin and regular users |
| `ontap_volumes_management` | Query and delete ONTAP volumes via the ONTAP proxy |
| `org_users` | Create / delete org users with role and scope (fleet/folder/org) assignment |
| `performance_policies` | Manage adaptive QoS performance policies |
| `protection_policies` | Manage data-protection policies |
| `query_working_environments` | List working environments in the org |
| `remove_system_from_fleet` | Detach ONTAP systems from a fleet |
| `scope_management` | Manage projects (scopes) within an organisation |
| `security_policies` | Manage security policies |
| `service_accounts` | Create / rotate / delete service accounts |
| `storage_classes` | Manage storage classes |
| `storage_fleets` | Create / update / delete fleets |
| `storage_provisioning` | Provision volumes and LUNs |
| `webhooks` | Manage outbound webhook notification endpoints |

> **Full parameter docs** for any module:
> ```bash
> ansible-doc netapp.console.storage_provisioning
> ansible-doc netapp.console.active_directory
> # etc.
> ```

### Example — provision a volume

```yaml
- name: Provision NFS volume
  netapp.console.storage_provisioning:
    console_url:          "{{ ncl_console_url }}"
    access_token:         "{{ ncl_access_token }}"
    org_id:               "{{ ncl_org_id }}"
    state:                present
    volume_name:          "my-vol"
    size_gb:              100
    protocol:             nfs
    validate_certs:       false
```

### Example — configure Active Directory

```yaml
- name: Ensure AD federation exists
  netapp.console.active_directory:
    console_url:          "{{ ncl_console_url }}"
    access_token:         "{{ ncl_access_token }}"
    org_id:               "{{ ncl_org_id }}"
    state:                present
    name:                 "corp-ad"
    connection_url:       "ldaps://dc.corp.com:636"
    bind_dn:              "administrator@corp.com"
    bind_credential:      "{{ vault_ad_password }}"
    users_dn:             "cn=Users,dc=corp,dc=com"
    skip_connection_test: true
    timeout:              300
    validate_certs:       false
```

---

## Playbooks Reference

Every playbook follows the same pattern:

1. **Auto-login** — skipped if `ncl_access_token` is already set.
2. **Auto-discover org** — skipped if `ncl_org_id` is set.
3. **Execute** the requested action.

| Playbook | Vars file | Key variable |
|---|---|---|
| `site.yml` | `ncl.yml` | Full bootstrap |
| `user_registration.yml` | `ncl.yml` | — |
| `fleet_management.yml` | `ncl_fleet.yml` | `ncl_fleet_action` |
| `fleet_delete.yml` | `ncl_fleet.yml` | — |
| `folder_management.yml` | `ncl.yml` | `ncl_folder_action` |
| `nested_folder_fleet.yml` | `ncl.yml` | — |
| `register_onprem_system.yml` | `ncl_register_onprem.yml` | — |
| `register_and_onboard.yml` | `ncl_register_and_onboard.yml` | — |
| `deregister_system.yml` | `ncl_deregister_system.yml` | — |
| `storage_provisioning.yml` | `ncl_storage_provisioning.yml` | `ncl_storage_action` |
| `volumes_delete.yml` | `ncl_volume_delete.yml` | — |
| `capacity_policies.yml` | `ncl_capacity_policy.yml` | `ncl_capacity_action` |
| `performance_policies.yml` | `ncl_performance_policy.yml` | `ncl_perf_action` |
| `protection_policies.yml` | `ncl_protection_policy.yml` | `ncl_protection_action` |
| `org_users.yml` | `ncl_org_users.yml` | `ncl_user_action` |
| `security_policies.yml` | `ncl_security_policy.yml` | `ncl_security_action` |
| `storage_classes.yml` | `ncl_storage_class.yml` | `ncl_sc_action` |
| `service_account.yml` | `ncl.yml` | `ncl_sa_action` |
| `llm_config.yml` | `ncl_llm.yml` | `ncl_llm_action` |
| `email_config.yml` | `ncl_email_config.yml` | `ncl_email_action` |
| `webhooks.yml` | `ncl_webhook.yml` | `ncl_webhook_action` |
| `active_directory.yml` | `ncl_active_directory.yml` | `ncl_ad_action` |

---

## Writing Your Own Playbooks

Once the collection is installed, you can write playbooks anywhere on your
machine — no special directory structure required. Use the FQCN
`netapp.console.<module_name>` and follow this pattern:

```yaml
---
- name: My custom NCL automation
  hosts: localhost
  connection: local        # all modules make REST calls from the control node
  gather_facts: false

  vars_files:
    - vars/ncl.yml         # shared appliance settings

  tasks:
    # Step 1 — always get a token first
    - name: Authenticate
      netapp.console.generate_oauth_token:
        console_url:    "{{ ncl_console_url }}"
        username:       "{{ ncl_admin_email }}"
        password:       "{{ ncl_admin_password }}"
        validate_certs: "{{ ncl_validate_certs }}"
      register: auth

    # Step 2 — pass the token to every subsequent module
    - name: Create a fleet
      netapp.console.storage_fleets:
        console_url:    "{{ ncl_console_url }}"
        access_token:   "{{ auth.access_token }}"
        org_id:         "{{ ncl_org_id }}"
        state:          present
        name:           "my-fleet"

    - name: Provision a volume
      netapp.console.storage_provisioning:
        console_url:    "{{ ncl_console_url }}"
        access_token:   "{{ auth.access_token }}"
        org_id:         "{{ ncl_org_id }}"
        state:          present
        volume_name:    "dev-vol-01"
        size_gb:        50
        protocol:       nfs
        validate_certs: "{{ ncl_validate_certs }}"
```

Key rules:
- Always `hosts: localhost` + `connection: local`
- Call `generate_oauth_token` first and `register` the result
- Pass `auth.access_token` to every subsequent task
- Use `ansible-doc netapp.console.<module>` for full parameter reference

---

## Secrets Management

Encrypt sensitive values with Ansible Vault:

```bash
# Encrypt the entire vars file
ansible-vault encrypt vars/ncl.yml

# Run with vault password
ansible-playbook playbooks/llm_config.yml \
    --extra-vars "@vars/ncl.yml" --ask-vault-pass

# Encrypt a single value inline
ansible-vault encrypt_string 'my-secret-key' --name ncl_llm_api_key
```

---

## Ansible Automation Platform (AAP / AWX)

For enterprise users running via **Red Hat AAP** or **AWX**:

1. Create a **Project** pointing to `https://github.com/NetApp/pace` (or your
   fork), path `ansible/console/local`.
2. AAP will detect `requirements.yml` and **automatically install
   `netapp.console`** before each job run — no manual Galaxy install needed.
3. Create a **Credential** of type *Vault* or *Machine* to inject
   `ncl_admin_password` and any other secrets.
4. Create a **Job Template** selecting the Project and one of the playbooks
   (e.g. `playbooks/storage_provisioning.yml`).
5. Pass `ncl_console_url`, `ncl_org_id`, etc. via **Survey** or **Extra
   Variables** in the Job Template.

> All NCL modules run on `localhost` (the control node / execution environment).
> No managed hosts or SSH credentials are required.

---

## Testing

```bash
# Unit tests
python -m pytest tests/ -v

# Ansible sanity (pep8, shebang, validate-modules, …)
# Requires: ansible-test (from ansible-core), run from collection source root
ansible-test sanity --python 3.11 2>&1 | tail -5

# Ansible-lint (production profile)
ansible-lint --profile production

# Validate module DOCUMENTATION blocks
ansible-doc netapp.console.storage_provisioning
```

> **Contributors:** use `make sanity`, `make lint`, `make validate-module` from
> the [internal source repo](https://github.com/NetApp/pace). All gates must be
> green before submitting a PR.

---

## License

GNU General Public License v3.0 or later — see [LICENSES/GPL-3.0-or-later.txt](LICENSES/GPL-3.0-or-later.txt).
