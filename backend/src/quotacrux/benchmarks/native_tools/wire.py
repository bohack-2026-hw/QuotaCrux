"""Numeric arrays across the sandbox boundary; no pickle or executable objects."""
import base64
import math
import numpy as np

MAX_ARRAY_BYTES = 128 * 1024 * 1024


def encode(value):
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "biufc" or value.nbytes > MAX_ARRAY_BYTES:
            raise ValueError("unsupported array dtype or size")
        return {"__array__": True, "dtype": value.dtype.str, "shape": list(value.shape),
                "data": base64.b64encode(value.tobytes()).decode()}
    if isinstance(value, np.generic):
        return encode(value.item())
    if isinstance(value, tuple):
        return {"__tuple__": [encode(v) for v in value]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise ValueError(f"unsupported value type: {type(value).__name__}")


def decode(value):
    if isinstance(value, dict):
        if value.get("__array__") is True:
            dtype = np.dtype(value["dtype"])
            shape = value["shape"]
            if dtype.kind not in "biufc" or not isinstance(shape, list) or len(shape) > 16:
                raise ValueError("invalid numeric array")
            if any(type(n) is not int or n < 0 for n in shape):
                raise ValueError("invalid array shape")
            size = math.prod(shape) * dtype.itemsize
            if size > MAX_ARRAY_BYTES or len(value["data"]) > (MAX_ARRAY_BYTES + 2) // 3 * 4:
                raise ValueError("array exceeds size limit")
            raw = base64.b64decode(value["data"], validate=True)
            if len(raw) != size:
                raise ValueError("array byte count does not match shape")
            return np.frombuffer(raw, dtype=dtype).reshape(shape).copy()
        if "__tuple__" in value:
            return tuple(decode(v) for v in value["__tuple__"])
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def finite(value):
    if isinstance(value, np.ndarray):
        return bool(np.isfinite(value).all())
    if isinstance(value, dict):
        return all(finite(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return all(finite(v) for v in value)
    return not isinstance(value, float) or math.isfinite(value)
