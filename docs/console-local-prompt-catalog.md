<!-- Generated from ai/console/local/prompt-catalog.md by scripts/generate_ai_assets.py. Do not edit; run `make ai-assets`. -->

# Console (local) prompt catalog

These are the publication-ready prompts for NetApp Console local deployment.
They cover the same observability and provisioning use cases as the working
draft list, with wording normalized and near-duplicate phrasings collapsed.

This catalog is a library of Console chat prompts, not Copilot or Cursor slash
commands. The assistant prompts that generate code in this repository live in
[`ai/shared/prompt-catalog.md`](../ai/shared/prompt-catalog.md).

Environment-specific identifiers such as cluster, SVM, volume, node, and
initiator names use angle-bracket placeholders. Substitute them with values
from your environment. Sizes, throughput limits, and built-in ONTAP policy
names are illustrative examples.

## Prompts

| # | Prompt | Category |
|---|--------|----------|
| 1 | Open the health dashboard | Observability |
| 2 | Give me an overall health summary for my organization | Observability |
| 3 | Is anything in my infrastructure currently unhealthy? | Observability |
| 4 | Summarize storage capacity and performance across my environment | Observability |
| 5 | Which critical alerts are active right now? | Observability |
| 6 | List every volume in my organization | Observability |
| 7 | Show me the details of volume `<volume-name>` | Observability |
| 8 | What is the capacity utilization of volume `<volume-name>`? | Observability |
| 9 | How is volume `<volume-name>` performing? | Observability |
| 10 | Is volume `<volume-name>` healthy? | Observability |
| 11 | Are any alerts raised against volume `<volume-name>`? | Observability |
| 12 | Give me a status report for fleet `<fleet-name>` | Observability |
| 13 | What is the capacity utilization of fleet `<fleet-name>`? | Observability |
| 14 | How is fleet `<fleet-name>` performing? | Observability |
| 15 | Is fleet `<fleet-name>` healthy? | Observability |
| 16 | Are any alerts raised against fleet `<fleet-name>`? | Observability |
| 17 | On cluster `<cluster-name>`, create an igroup named `<igroup-name>` on SVM `<svm-name>` with OS type linux and protocol iscsi, add initiator `<initiator-iqn>`, and map LUN `<lun-name>` to it | Provisioning |
| 18 | On cluster `<cluster-name>`, enable the FCP service on SVM `<svm-name>` and create an FC interface named `<interface-name>` on port `<port-name>` of node `<node-name>` using the fcp data protocol | Provisioning |
| 19 | On cluster `<cluster-name>`, create a cron schedule named `<schedule-name>` with the expression `0 0,4,8,12,16,20 * * *`, then create a snapshot policy named `<snapshot-policy-name>` on SVM `<svm-name>` that uses this schedule and retains 5 snapshots | Provisioning |
| 20 | On cluster `<cluster-name>`, create an NFS export policy named `<export-policy-name>` on SVM `<svm-name>` with a rule that matches clients `0.0.0.0/0` and allows read-only and read-write access to any | Provisioning |
| 21 | On cluster `<cluster-name>`, create a fixed QoS policy named `<qos-policy-name>` on SVM `<svm-name>` with a maximum throughput of 5000 IOPS and apply it to volume `<volume-name>` | Provisioning |
| 22 | On cluster `<cluster-name>`, create a SnapMirror relationship from SVM `<source-svm-name>` volume `<source-volume-name>` to SVM `<destination-svm-name>` volume `<destination-volume-name>` using the MirrorAllSnapshots policy, then initialize it | Provisioning |
| 23 | On cluster `<cluster-name>`, resize volume `<volume-name>` on SVM `<svm-name>` to 50 MB and then take a snapshot named `<snapshot-name>` | Provisioning |
| 24 | On cluster `<cluster-name>`, create the NVMe service on SVM `<svm-name>`, add subsystem `<subsystem-name>` with linux OS, register host NQN `<host-nqn>` against it, create a 20 MB namespace at `/vol/<volume-name>/<namespace-name>` with linux OS, and map subsystem `<subsystem-name>` to that namespace | Provisioning |
| 25 | On cluster `<cluster-name>`, create a qtree named `<qtree-name>` inside volume `<volume-name>` on SVM `<svm-name>` and apply the performance QoS policy to that volume | Provisioning |
| 26 | Provision a 20 GB LUN for my database server, create an igroup named `<igroup-name>` for linux iscsi, and map the LUN to that igroup | Provisioning |
| 27 | I need block storage for a VMware ESXi host: provision a LUN, create a vmware igroup named `<igroup-name>` with initiator `<initiator-iqn>`, and map the LUN to it | Provisioning |
| 28 | Provision a 500 GB NFS volume for the finance team and attach an hourly snapshot policy that retains 5 snapshots | Provisioning |
| 29 | Create a 1 TB volume for production data and replicate it to SVM `<destination-svm-name>` as volume `<destination-volume-name>` using the XDPDefault policy | Provisioning |
| 30 | Provision a 100 GB LUN for an Oracle database and apply a fixed QoS policy capped at 3000 IOPS to the volume that hosts it | Provisioning |
