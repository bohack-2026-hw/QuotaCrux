"""Renaming the app must preserve access to existing local research records."""

import json
import subprocess
import sys

import pytest


def read_paths(env):
    result = subprocess.run(
        [sys.executable, "-c", "from quotacrux import config; import json; "
         "print(json.dumps([str(config.VAR_DIR), str(config.DB_PATH)]))"],
        env=env, check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("key", ["QUOTACRUX_VAR_DIR", "ROUTEEVO_VAR_DIR"])
def test_existing_database_is_reused(tmp_path, key):
    legacy = tmp_path / "routeevo.sqlite3"
    legacy.touch()
    assert read_paths({key: str(tmp_path)}) == [str(tmp_path), str(legacy)]


def test_new_name_takes_precedence(tmp_path):
    current = tmp_path / "quotacrux.sqlite3"
    current.touch()
    (tmp_path / "routeevo.sqlite3").touch()
    assert read_paths({
        "QUOTACRUX_VAR_DIR": str(tmp_path), "ROUTEEVO_VAR_DIR": str(tmp_path / "old"),
    }) == [str(tmp_path), str(current)]


def test_new_store_uses_new_name(tmp_path):
    assert read_paths({"QUOTACRUX_VAR_DIR": str(tmp_path)}) == [
        str(tmp_path), str(tmp_path / "quotacrux.sqlite3"),
    ]
