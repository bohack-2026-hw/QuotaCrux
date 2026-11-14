import numpy as np
from scipy.fft import rfft, irfft, next_fast_len


def solve(problem):
    a, b = problem
    na, nb = len(a), len(b)
    if min(na, nb) <= 32 or na * nb <= 8192:
        return np.convolve(a, b, mode='full')
    if na < nb:
        a, b = b, a
        na, nb = nb, na
    size = na + nb - 1

    if size >= 32768 and nb >= 1024 and 2 * nb <= na <= 8 * nb:
        minimum = (na + 3) // 4 + nb - 1
        n = 1 << (minimum - 1).bit_length()
        block = n - nb + 1
        count = (na + block - 1) // block
        x = np.zeros((count + 1, n), dtype=np.float64)
        x[count, :nb] = b
        for i in range(count):
            start = i * block
            stop = min(start + block, na)
            x[i, :stop - start] = a[start:stop]
        f = rfft(x, axis=1, workers=4, overwrite_x=True)
        spectra = f[:count]
        spectra *= f[count]
        pieces = irfft(spectra, n=n, axis=1, workers=4, overwrite_x=True)
        result = np.zeros(size, dtype=np.float64)
        for i in range(count):
            start = i * block
            length = min(block, na - start) + nb - 1
            result[start:start + length] += pieces[i, :length]
        return result

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
