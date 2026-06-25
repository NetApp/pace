# ONTAP in 5 minutes

Just enough NetApp ONTAP vocabulary to read the examples in this repo.
You do **not** need to read this end-to-end — every example file links
back here from a "Concepts used" comment at the top, and each per-style
README cross-references the relevant terms.

For the full picture, NetApp's official docs are at
[docs.netapp.com/us-en/ontap](https://docs.netapp.com/us-en/ontap/).

---

## Cluster

A group of one or more **nodes** (storage controllers) that present
themselves as a single system. Has one management IP and one set of
admin credentials. Every example targets a single cluster via
`ONTAP_HOST`. → seen in: every example.

## Node

A physical (or virtual) controller that owns disks and serves data.
A cluster is a set of nodes. The free **ONTAP Simulator** runs as a
single virtual node and is good enough for most provisioning examples.

## SVM (Storage Virtual Machine)

A logical "tenant" inside a cluster. Like a VM inside a hypervisor —
isolated namespace, own users, own volumes, own data IPs. NFS exports
and CIFS shares always belong to an SVM. Most provisioning examples
default to an SVM named `svm0`. → seen in:
[`python/nfs_provision.py`](../python/nfs_provision.py),
[`ansible/cifs_provision.yml`](../ansible/cifs_provision.yml).

## Aggregate

A pool of physical disks. Volumes live inside aggregates.
Think: "disk farm + RAID group". You don't usually create one in
these examples — you reference an existing one with `--aggregate aggr1`.
List them on a cluster with `storage aggregate show`.

## Volume

The unit of storage that holds your files. Lives inside an aggregate
and inside an SVM. Has a size, an export path (for NFS) or share path
(for CIFS), and snapshot policies. → seen in: every provisioning
example.

## LIF (Logical Interface)

A floating IP that data clients (NFS, CIFS, iSCSI) connect to.
Like a Kubernetes Service IP — it survives node failover by moving to
another node. Provisioning examples create or reference data LIFs to
expose new shares.

## Export policy (NFS)

The ACL controlling which clients (by IP / subnet) can mount an NFS
volume and with what permissions. The default `default` policy is
typically too permissive for production — examples expose
`--client-match` to override. → seen in:
[`python/nfs_provision.py`](../python/nfs_provision.py).

## CIFS / SMB share

Windows-style file share served by an SVM. Each share has a name, a
backing volume path, and an ACL. → seen in:
[`python/cifs_provision.py`](../python/cifs_provision.py).

## Snapshot

A point-in-time, copy-on-write image of a volume. Cheap to take, fast
to restore from. Forms the basis for backup, cloning, and replication.

## SnapMirror

ONTAP's volume-level replication. Copies snapshots from a source volume
on one cluster to a destination volume on another, for DR or migration.
Pace ships full source-managed and destination-managed examples plus a
test-failover lifecycle. → seen in:
[`ansible/snapmirror_provision_src_managed.yml`](../ansible/snapmirror_provision_src_managed.yml).

## REST API

ONTAP 9.6+ exposes a full REST API at `https://<cluster>/api/`. Every
Pace example uses this — never SSH, ZAPI, or CLI passthrough.
Long-running operations return a job UUID; you poll
`/api/cluster/jobs/{uuid}` until state is `success` or `failure`.
See [docs/ontap-api-patterns.md](ontap-api-patterns.md) for the full
conventions.

## RBAC role

ONTAP's permission model. The built-in `admin` role can do anything;
purpose-built roles let you grant least-privilege access to a specific
endpoint set. List with `security login role show`.

---

## Where these show up in the examples

| Example | Concepts used |
|---|---|
| [`cluster_info.py`](../python/cluster_info.py) | Cluster, Node, REST API |
| [`cluster_setup.yml`](../ansible/cluster_setup.yml) | Cluster, Node, LIF, Aggregate, RBAC |
| [`cluster_setup_basic/main.go`](../go/cluster_setup_basic/main.go) | Cluster, Node, REST API jobs |
| [`nfs_provision.*`](../python/nfs_provision.py) | SVM, Aggregate, Volume, LIF, Export policy |
| [`cifs_provision.*`](../python/cifs_provision.py) | SVM, Aggregate, Volume, LIF, CIFS share |
| [`snapmirror_*`](../ansible/snapmirror_provision_src_managed.yml) | Volume, Snapshot, SnapMirror, REST API jobs |

---

> Need a term that is not in this list? Open a
> [Discussion](https://github.com/NetApp/pace/discussions) and we will
> add it. Keeping this page to a single screen is intentional — if it
> grows past ~12 terms it stops being a 5-minute read.
