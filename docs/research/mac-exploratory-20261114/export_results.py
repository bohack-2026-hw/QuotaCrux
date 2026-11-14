#!/usr/bin/env python3
"""Export the 2026-11-14 Mac exploratory ledgers into a portable evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Batch:
    name: str
    source: str
    destination: str
    comparison: str


BATCHES = (
    Batch("openai", "exploratory-short-20261114", "openai", "research-20261114T085753-86f4.json"),
    Batch("remote-preload", "remote-lmstudio-short-20261114", "remote/01-preload-proxy", "research-20261114T090917-d7d3.json"),
    Batch("remote-loaded", "remote-lmstudio-retry-20261114", "remote/02-loaded-proxy", "research-20261114T091202-fa2b.json"),
    Batch("remote-bounded", "remote-lmstudio-finaltry-20261114", "remote/03-bounded-proxy", "research-20261114T091639-a966.json"),
    Batch("remote-direct", "remote-lmstudio-direct-20261114", "remote/04-direct", "research-20261114T091800-0fe2.json"),
)

TASK_PUBLIC_FILES = (
    "UPSTREAM_LICENSE.txt",
    "contract.txt",
    "dev_profile.json",
    "examples.json",
    "initial.py",
    "manifest.json",
    "upstream_task.py",
)

NULL_RESPONSE_FIELDS = {"user", "safety_identifier", "prompt_cache_key"}
OPENAI_OPAQUE_ID = re.compile(
    r"(?<![A-Za-z0-9_])(?:resp|rs|msg)_[A-Za-z0-9_-]+(?![A-Za-z0-9_-])"
)
OPENAI_OPAQUE_ID_FULL = re.compile(r"(?:resp|rs|msg)_[A-Za-z0-9_-]+\Z")
IPV4 = re.compile(
    r"(?<![0-9.])(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})"
    r"(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3}(?![0-9.])"
)
URL_IPV4_ENDPOINT = re.compile(
    r"(?P<scheme>https?)://(?P<address>(?:[0-9]{1,3}\.){3}[0-9]{1,3})(?::[0-9]{1,5})?"
)
LMSTUDIO_IPV4_ENDPOINT = re.compile(
    r"local://lmstudio/(?P<address>(?:[0-9]{1,3}\.){3}[0-9]{1,3})(?::[0-9]{1,5})?"
)
BRACKETED_IPV6 = re.compile(r"\[(?P<address>[0-9A-Fa-f:.%]+)\]")
POSSIBLE_IPV6 = re.compile(
    r"(?<![0-9A-Fa-f:])(?=[0-9A-Fa-f:]*:)[0-9A-Fa-f:]{2,}(?![0-9A-Fa-f:])"
)
LOCAL_CHECKOUT = re.compile(
    r"/(?:Users|home)/[^/\s\"']+(?:/[^/\s\"']+)*/RouteEvo"
    r"(?=(?:[/\s\"']|$))"
)
UNIX_HOME = re.compile(r"/(?:Users|home)/[^/\s\"']+")
WINDOWS_CHECKOUT = re.compile(
    r"[A-Za-z]:\\Users\\[^\\\s\"']+(?:\\[^\\\s\"']+)*\\RouteEvo"
    r"(?=(?:[\\\s\"']|$))",
    re.IGNORECASE,
)
WINDOWS_HOME = re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"']+", re.IGNORECASE)
ENCRYPTED_CONTENT_FIELD = re.compile(
    r'(?m)(?:^[ \t]*)?"encrypted_content"\s*:\s*"(?:\\.|[^"\\])*"\s*,?\r?\n?'
)
NULL_RESPONSE_FIELD = re.compile(
    r'(?m)(?:^[ \t]*)?"(?:user|safety_identifier|prompt_cache_key)"\s*:\s*null\s*,?\r?\n?'
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _redact_ip(address: str) -> str:
    candidate = address.split("%", 1)[0]
    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError:
        return address
    return "localhost" if parsed.is_loopback else "<REDACTED_IP>"


def _redact_bracketed_ipv6(match: re.Match[str]) -> str:
    address = match.group("address")
    try:
        ipaddress.IPv6Address(address.split("%", 1)[0])
    except ValueError:
        return match.group(0)
    return _redact_ip(address)


def _redact_local_checkout(match: re.Match[str]) -> str:
    path = match.group(0)
    normalized = path.replace("\\", "/")
    return "<EXECUTION_CHECKOUT>" if "/.codex/worktrees/" in normalized else "<SOURCE_CHECKOUT>"


def _redact_url_endpoint(match: re.Match[str]) -> str:
    try:
        address = ipaddress.ip_address(match.group("address"))
    except ValueError:
        return match.group(0)
    if address.is_loopback:
        host = "system-proxy.invalid"
    elif address.is_link_local:
        host = "remote-lmstudio.invalid"
    else:
        host = "redacted-endpoint.invalid"
    return f'{match.group("scheme")}://{host}'


def _redact_lmstudio_endpoint(match: re.Match[str]) -> str:
    try:
        address = ipaddress.ip_address(match.group("address"))
    except ValueError:
        return match.group(0)
    host = "thunderbolt-bridge" if address.is_link_local else "redacted-peer"
    return f"local://lmstudio/{host}"


def sanitize_text(text: str, var_dir: Path, evidence_dir: Path) -> str:
    text = text.replace(str(var_dir), "<VAR_DIR>").replace(str(evidence_dir), "<EVIDENCE_DIR>")
    text = LOCAL_CHECKOUT.sub(_redact_local_checkout, text)
    text = WINDOWS_CHECKOUT.sub(_redact_local_checkout, text)
    text = UNIX_HOME.sub("<LOCAL_HOME>", text)
    text = WINDOWS_HOME.sub("<LOCAL_HOME>", text)
    text = URL_IPV4_ENDPOINT.sub(_redact_url_endpoint, text)
    text = LMSTUDIO_IPV4_ENDPOINT.sub(_redact_lmstudio_endpoint, text)
    text = BRACKETED_IPV6.sub(_redact_bracketed_ipv6, text)
    text = POSSIBLE_IPV6.sub(lambda match: _redact_ip(match.group(0)), text)
    text = IPV4.sub(lambda match: _redact_ip(match.group(0)), text)
    text = OPENAI_OPAQUE_ID.sub("<OPENAI_OPAQUE_ID>", text)
    text = ENCRYPTED_CONTENT_FIELD.sub("", text)
    return NULL_RESPONSE_FIELD.sub("", text)


def sanitize(value: Any, var_dir: Path, evidence_dir: Path) -> Any:
    if isinstance(value, dict):
        public: dict[str, Any] = {}
        for key, item in value.items():
            if key == "encrypted_content":
                continue
            if key in NULL_RESPONSE_FIELDS and item is None:
                continue
            if isinstance(item, str) and OPENAI_OPAQUE_ID_FULL.fullmatch(item):
                continue
            public[key] = sanitize(item, var_dir, evidence_dir)
        return public
    if isinstance(value, list):
        return [
            sanitize(item, var_dir, evidence_dir)
            for item in value
            if not (isinstance(item, str) and OPENAI_OPAQUE_ID_FULL.fullmatch(item))
        ]
    if isinstance(value, str):
        return sanitize_text(value, var_dir, evidence_dir)
    return value


def write_json(source: Path, destination: Path, var_dir: Path, evidence_dir: Path) -> None:
    value = json.loads(source.read_text())
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(sanitize(value, var_dir, evidence_dir), ensure_ascii=False, indent=2) + "\n")


def write_text(source: Path, destination: Path, var_dir: Path, evidence_dir: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    text = data.decode("utf-8")
    if source.suffix == ".py":
        if sanitize_text(text, var_dir, evidence_dir) != text:
            raise ValueError(f"program requires manual privacy review; cannot preserve bytes: {source.name}")
        destination.write_bytes(data)
        return
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        destination.write_text(sanitize_text(text, var_dir, evidence_dir))
    else:
        destination.write_text(json.dumps(sanitize(value, var_dir, evidence_dir), ensure_ascii=False, indent=2) + "\n")


def copy_portable(source: Path, destination: Path, var_dir: Path, evidence_dir: Path) -> None:
    if source.suffix == ".json":
        write_json(source, destination, var_dir, evidence_dir)
    else:
        write_text(source, destination, var_dir, evidence_dir)


def export_sqlite(db_path: Path, destination: Path, var_dir: Path, evidence_dir: Path) -> None:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    schemas = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    tables: dict[str, list[dict[str, Any]]] = {}
    for schema in schemas:
        rows = connection.execute(f'SELECT * FROM "{schema["name"]}"').fetchall()
        public_rows = []
        for row in rows:
            public_row = dict(row)
            if schema["name"] == "model_calls":
                public_row.pop("request_id", None)
            public_rows.append(public_row)
        tables[schema["name"]] = public_rows
    snapshot = {
        "format": "routeevo-sqlite-json-v1",
        "source_binary_committed": False,
        "schemas": {row["name"]: row["sql"] for row in schemas},
        "tables": tables,
    }
    destination.write_text(json.dumps(sanitize(snapshot, var_dir, evidence_dir), ensure_ascii=False, indent=2) + "\n")
    connection.close()


def export_task(task_dir: Path, destination: Path, var_dir: Path, evidence_dir: Path) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((task_dir / "manifest.json").read_text())
    for name in TASK_PUBLIC_FILES:
        source = task_dir / name
        if source.exists():
            copy_portable(source, destination / name, var_dir, evidence_dir)
    files = {
        path.name: {"sha256": sha256(path), "bytes": path.stat().st_size, "content_committed": path.name in TASK_PUBLIC_FILES}
        for path in sorted(task_dir.iterdir())
        if path.is_file()
    }
    identity = {
        "task_id": manifest["task_id"],
        "canonical_manifest_sha256": canonical_json_sha256(manifest),
        "selection": manifest["selection"],
        "source": manifest["source"],
        "native": manifest.get("native"),
        "files": files,
        "sealed_dataset_policy": "dev/final inputs are identified by hash and byte count; raw datasets are not committed",
    }
    (destination / "task-identity.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2) + "\n")
    return identity


def export_batch(batch: Batch, runs_root: Path, evidence_root: Path, output_root: Path) -> dict[str, Any]:
    var_dir = runs_root / batch.source
    evidence_dir = evidence_root / batch.source
    destination = output_root / batch.destination
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite {destination}")
    destination.mkdir(parents=True)

    comparison_path = var_dir / "comparisons" / batch.comparison
    comparison = json.loads(comparison_path.read_text())
    write_json(comparison_path, destination / "comparison.json", var_dir, evidence_dir)

    evidence_destination = destination / "evidence"
    for source in sorted(evidence_dir.iterdir()):
        if source.is_file():
            copy_portable(source, evidence_destination / source.name, var_dir, evidence_dir)

    run_ids: list[str] = []
    for row in comparison["runs"]:
        run_id = row.get("run_id")
        if not run_id:
            continue
        run_ids.append(run_id)
        run_source = var_dir / "runs" / run_id
        run_destination = destination / "runs" / run_id
        write_json(run_source / "report.json", run_destination / "report.json", var_dir, evidence_dir)
        for subdirectory in ("calls", "candidates"):
            for source in sorted((run_source / subdirectory).glob("*")):
                copy_portable(source, run_destination / subdirectory / source.name, var_dir, evidence_dir)
        report = json.loads((run_source / "report.json").read_text())
        best = report.get("best_candidate")
        if best:
            best_path = run_source / "candidates" / f'{best["candidate_id"]}.py'
            if best_path.exists():
                write_text(best_path, run_destination / "best.py", var_dir, evidence_dir)

    task_identities = []
    for task_dir in sorted((var_dir / "tasks").iterdir()):
        if task_dir.is_dir():
            task_identities.append(export_task(task_dir, destination / "tasks" / task_dir.name, var_dir, evidence_dir))

    export_sqlite(var_dir / "routeevo.sqlite3", destination / "ledger.json", var_dir, evidence_dir)
    inventory = {
        "batch": batch.name,
        "source_directory_name": batch.source,
        "comparison_id": comparison["comparison_id"],
        "run_ids": run_ids,
        "task_ids": [item["task_id"] for item in task_identities],
        "included": [
            "comparison",
            "all evidence files including the captured CLI log",
            "all run reports",
            "all model call request/response JSON",
            "all candidate programs",
            "portable JSON snapshot of every SQLite table",
            "task manifests, public task metadata and dataset hashes",
        ],
        "excluded": {
            "sqlite_wal_shm": "replaced by ledger.json because the binary files contain machine-local paths",
            "raw_dev_and_final_inputs": "sealed inputs are represented by task-identity hashes and byte counts",
            "locks": "empty runtime coordination files are not result evidence",
        },
    }
    (destination / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
    return inventory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--diagnostics-root", type=Path)
    args = parser.parse_args()

    inventories = [export_batch(batch, args.runs_root, args.evidence_root, args.output) for batch in BATCHES]
    diagnostics = []
    if args.diagnostics_root:
        destination = args.output / "remote" / "diagnostics"
        for name in ("routeevo-lms-full-response", "routeevo-lms-nothink-response"):
            source = args.diagnostics_root / name
            if source.exists():
                write_json(source, destination / f"{name}.json", Path("/nonexistent"), Path("/nonexistent"))
                diagnostics.append(f"remote/diagnostics/{name}.json")
    manifest = {
        "format": "routeevo-mac-exploratory-export-v1",
        "execution_code_sha": "912b20a4cfeb51af9c36d0679b23f0990abe862f",
        "formal_results_eligible": False,
        "batches": inventories,
        "diagnostics": diagnostics,
    }
    (args.output / "export-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
