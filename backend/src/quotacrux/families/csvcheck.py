"""Output check shared by the CSV-producing families added after groupagg (same result shape as groupagg's checker)."""

from __future__ import annotations


def _parse(text: str, header: str, n_fields: int, int_fields: tuple[int, ...]) -> tuple[list[str] | None, dict | None]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    if not lines or lines[0] != header:
        got = lines[0][:80] if lines else ""
        return None, {"category": "format_error", "message": f"first line must be {header!r}, got {got!r}"}
    for i, line in enumerate(lines[1:], start=2):
        parts = line.split(",")
        if len(parts) != n_fields:
            return None, {"category": "format_error", "message": f"line {i} must have {n_fields} fields: {line[:80]!r}"}
        try:
            for j in int_fields:
                int(parts[j])
        except ValueError:
            return None, {"category": "format_error", "message": f"line {i} has a non-integer numeric field: {line[:80]!r}"}
    return lines[1:], None


def check_keyed_csv(stdout: bytes, expected: bytes, *, header: str, key_fields: int, int_fields: tuple[int, ...],
                    max_examples: int = 3) -> dict:
    """Return {format_ok, correct, failure}. A row's key is its first `key_fields` fields."""
    if stdout == expected:
        return {"format_ok": True, "correct": True, "failure": None}
    n_fields = len(header.split(","))
    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {"format_ok": False, "correct": False, "failure": {"category": "format_error", "message": f"output is not UTF-8: {exc}"}}
    got, err = _parse(text, header, n_fields, int_fields)
    if err:
        return {"format_ok": False, "correct": False, "failure": err}
    want, _ = _parse(expected.decode("ascii"), header, n_fields, int_fields)
    assert want is not None
    if got == want:
        return {"format_ok": True, "correct": True, "failure": None}

    def key(line: str) -> str:
        return ",".join(line.split(",")[:key_fields])

    got_map = {key(line): line for line in got}
    want_map = {key(line): line for line in want}
    missing = [k for k in want_map if k not in got_map]
    extra = [k for k in got_map if k not in want_map]
    wrong = [k for k in want_map if k in got_map and got_map[k] != want_map[k]]
    duplicated = len(got) - len(got_map)
    categories = [c for c, hit in (("missing_keys", missing), ("extra_keys", extra), ("wrong_values", wrong),
                                   ("duplicate_keys", duplicated)) if hit] or ["wrong_order"]
    examples = [{"key": k, "expected": want_map[k], "got": got_map[k]} for k in wrong[:max_examples]]
    examples += [{"key": k, "expected": want_map[k], "got": None} for k in missing[: max(0, max_examples - len(examples))]]
    examples += [{"key": k, "expected": None, "got": got_map[k]} for k in extra[: max(0, max_examples - len(examples))]]
    return {
        "format_ok": True,
        "correct": False,
        "failure": {
            "category": "wrong_output", "kinds": categories, "expected_groups": len(want), "output_lines": len(got),
            "missing_keys": len(missing), "extra_keys": len(extra), "wrong_value_keys": len(wrong),
            "duplicated_lines": duplicated, "examples": examples,
        },
    }
