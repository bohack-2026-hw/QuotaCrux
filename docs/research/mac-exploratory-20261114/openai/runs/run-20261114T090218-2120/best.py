import numpy as np
from scipy.fft import rfft, irfft, next_fast_len


def _double(a, b, size, n):
    fa = rfft(a, n=n)
    fb = rfft(b, n=n)
    fa *= fb
    return irfft(fa, n=n, overwrite_x=True)[:size]


def solve(problem):
    a, b = problem
    la, lb = len(a), len(b)
    if la * lb <= 8192:
        return np.convolve(a, b, mode='full')
    size = la + lb - 1
    n = next_fast_len(size, real=True)
    ma = np.max(np.abs(a))
    mb = np.max(np.abs(b))
    if ma == 0 or mb == 0:
        return np.zeros(size, dtype=np.float64)
    if not (1e-4 <= ma <= 1e4 and 1e-4 <= mb <= 1e4):
        return _double(a, b, size, n)
    aa = a.astype(np.float32)
    bb = b.astype(np.float32)
    ea = float(np.dot(aa, aa))
    eb = float(np.dot(bb, bb))
    fa = rfft(aa, n=n, overwrite_x=True)
    fb = rfft(bb, n=n, overwrite_x=True)
    fa *= fb
    result = irfft(fa, n=n, overwrite_x=True)[:size]
    er = float(np.dot(result, result))
    if not (er >= 0.02 * ea * eb and np.isfinite(er)):
        return _double(a, b, size, n)
    return result.astype(np.float64)
