"""Pytest configuration — make the python/ directory importable without installing."""

from __future__ import annotations

import sys
from pathlib import Path

# Add python/ to sys.path so test modules can import ontap_client, nfs_provision, etc.
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))
