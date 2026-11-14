import numpy as np
from scipy import signal

def solve(problem):
    a, b = problem
    # Use FFT-based convolution for potentially better performance
    n = len(a) + len(b) - 1
    # Next power of 2 for efficient FFT
    fft_size = 1 << (n - 1).bit_length()
    fa = np.fft.rfft(a, fft_size)
    fb = np.fft.rfft(b, fft_size)
    fc = fa * fb
    result = np.fft.irfft(fc, fft_size)[:n]
    return result