import numpy as np

def solve(problem):
    a, b = problem
    n = len(a) + len(b) - 1
    # Use next power of 2 for FFT size for efficiency
    fft_size = 1
    while fft_size < n:
        fft_size <<= 1
    fa = np.fft.rfft(a, fft_size)
    fb = np.fft.rfft(b, fft_size)
    result = np.fft.irfft(fa * fb, fft_size)[:n]
    return result