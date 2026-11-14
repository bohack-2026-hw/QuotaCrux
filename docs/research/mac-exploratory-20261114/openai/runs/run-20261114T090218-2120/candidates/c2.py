import numpy as np
from scipy.fft import rfft, irfft, next_fast_len


def _double(a, b, size, nfft):
    fa = rfft(a, n=nfft)
    fb = rfft(b, n=nfft)
    fa *= fb
    return irfft(fa, n=nfft, overwrite_x=True)[:size]


def solve(problem):
    a, b = problem
    na, nb = len(a), len(b)
    size = na + nb - 1
    if min(na, nb) <= 32 or na * nb <= 8192:
        return np.convolve(a, b)
    nfft = next_fast_len(size, real=True)
    if nfft > 262144:
        return _double(a, b, size, nfft)
    ea = float(np.einsum('i,i->', a, a))
    eb = float(np.einsum('i,i->', b, b))
    if not (1e-24 < ea < 1e24 and 1e-24 < eb < 1e24):
        return _double(a, b, size, nfft)
    fa = rfft(np.asarray(a, dtype=np.float32), n=nfft)
    fb = rfft(np.asarray(b, dtype=np.float32), n=nfft)
    fa *= fb
    result = irfft(fa, n=nfft, overwrite_x=True)[:size]
    ec = float(np.einsum('i,i->', result, result, dtype=np.float64))
    if not (ec >= 0.5 * ea * eb and np.isfinite(ec)):
        return _double(a, b, size, nfft)
    return result
