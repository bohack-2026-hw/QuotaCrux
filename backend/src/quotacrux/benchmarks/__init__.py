"""Task-specific data and correctness for the runtime optimization loop."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    name: str
    input: bytes
    expected: bytes


def get(family: str):
    from .. import families

    if family in families.REGISTRY:
        from .generated import GeneratedBenchmark
        return GeneratedBenchmark(families.get(family))
    if family == "effibench-x":
        from . import effibench
        return effibench
    if family == "ale-bench":
        from . import ale
        return ale
    if family == "algotune":
        from . import algotune
        return algotune
    if family == "kernelbench":
        from . import kernelbench
        return kernelbench
    raise ValueError(f"unsupported family {family!r}")
