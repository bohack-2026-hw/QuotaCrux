import numpy as np
from scipy.fft import rfft, irfft, next_fast_len


def solve(problem):
    a, b = problem
    na, nb = len(a), len(b)
    if min(na, nb) <= 32 or na * nb <= 8192:
        return np.convolve(a, b, mode='full')
    size = na + nb - 1
    n = next_fast_len(size, real=True)
    if n < 16384:
        fa = rfft(a, n=n)
        fb = rfft(b, n=n)
        fa *= fb
        return irfft(fa, n=n, overwrite_x=True)[:size]
    x = np.empty((2, n), dtype=np.float64)
    x[0, :na] = a
    x[0, na:] = 0.0
    x[1, :nb] = b
    x[1, nb:] = 0.0
    f = rfft(x, axis=1, workers=2, overwrite_x=True)
    f0 *= f1
    return irfft(f0, n=n, overwrite_x=True)[:size]
