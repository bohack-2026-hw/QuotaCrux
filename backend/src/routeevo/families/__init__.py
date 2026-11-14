"""Task families. Each module provides one kind of program to optimize: contract, initial program, data generator,
trusted reference output, workload profile and condition buckets, public contract cases and output checker."""

from __future__ import annotations

from types import ModuleType

from . import groupagg, intervals, logstats

REGISTRY: dict[str, ModuleType] = {m.FAMILY: m for m in (groupagg, logstats, intervals)}


def get(name: str) -> ModuleType:
    try:
        return REGISTRY[name]
    except KeyError:
        raise ValueError(f"unsupported family {name!r}; known: {sorted(REGISTRY)}") from None
