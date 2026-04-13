#!/usr/bin/env python3
"""
<Use Case Name> — brief description of what this script does.

Prerequisites:
    pip install -r requirements.txt
    export ONTAP_HOST=10.0.0.1 ONTAP_USER=admin ONTAP_PASS=changeme

Usage:
    python example.py [--flag value]
"""

import logging
import sys

from ontap_client import OntapClient

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    with OntapClient.from_env() as client:
        # 1. Retrieve or create resources
        resp = client.get("/api/cluster", params={"fields": "name,version"})
        cluster = resp.json()
        log.info("Cluster: %s — %s", cluster["name"], cluster["version"]["full"])

        # 2. Add your logic here
        # ...


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
