import numpy as np
from scipy import fftpack

def solve(problem):
    a, b = problem
    n = len(a) + len(b) - 1
    fft_size = fftpack.next_fast_len(n)
    fa = fftpack.rfft(a, fft_size)
    fb = fftpack.rfft(b, fft_size)
    fc = fa * fb
    result = fftpack.irfft(fc, fft_size)[:n]
    return result