import numpy as np
from scipy import fftpack

def solve(problem):
    a, b = problem
    n = len(a) + len(b) - 1
    fft_size = fftpack.next_fast_len(n)
    fa = np.fft.rfft(a, fft_size)
    fb = np.fft.rfft(b, fft_size)
    fa *= fb
    result = np.fft.irfft(fa, fft_size)[:n]
    return result