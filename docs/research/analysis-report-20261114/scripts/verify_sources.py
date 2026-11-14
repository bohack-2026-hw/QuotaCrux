#!/usr/bin/env python3
"""Verify the archived desktop evidence manifests without running any benchmark."""
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parents[4]
directories = [
    root / 'docs/research/native-formal-20261114/ale/results',
    root / 'docs/research/native-routing/20261114/short-results',
    root / 'docs/research/native-routing/20261114/long-batch-stopped',
]
total = 0
for directory in directories:
    entries = (directory / 'SHA256SUMS').read_text().splitlines()
    for line in entries:
        expected, relative = line.split(maxsplit=1)
        artifact = directory / relative.lstrip('*')
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f'Checksum mismatch: {artifact}')
    total += len(entries)
    print(f'{directory.relative_to(root)}: {len(entries)} checksums matched')
print(f'Archived evidence: {total} checksum entries matched; no benchmark executed.')
