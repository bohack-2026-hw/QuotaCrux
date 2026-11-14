"""Task-specific data and correctness for the runtime optimization loop."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    name: str
    input: bytes
    expected: bytes


def get(family: str):
    if family == "groupagg":
        from . import groupagg
        return groupagg
    if family == "effibench-x":
        from . import effibench
        return effibench
    raise ValueError(f"unsupported family {family!r}")
