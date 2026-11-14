import numpy as np
from scipy.fft import rfft, irfft, next_fast_len


def solve(problem):
    a, b = problem
    na, nb = len(a), len(b)
    if min(na, nb) <= 32 or na * nb <= 8192:
        return np.convolve(a, b, mode='full')
    size = na + nb - 1
    n = next_fast_len(size, real=True)
    fa = rfft(a, n=n)
    fb = rfft(b, n=n)
    fa *= fb
    return irfft(fa, n=n, overwrite_x=True)[:size]
