import numpy as np
from scipy.fft import next_fast_len
from scipy.fft._pocketfft import pypocketfft as _pfft


def solve(problem):
    a, b = problem
    na = len(a)
    nb = len(b)
    if min(na, nb) <= 32:
        return np.convolve(a, b, mode='full')

    size = na + nb - 1
    n = next_fast_len(size, real=True)
    work = np.empty(n, dtype=np.float64)
    work[:na] = a
    work[na:] = 0.0
    fa = _pfft.r2c(work, axes=(0,), forward=True, inorm=0, nthreads=1)
    work[:nb] = b
    work[nb:] = 0.0
    fb = _pfft.r2c(work, axes=(0,), forward=True, inorm=0, nthreads=1)
    np.multiply(fa, fb, out=fa)
    _pfft.c2r(fa, axes=(0,), lastsize=n, forward=False, inorm=2,
              out=work, nthreads=1)
    return work[:size]
