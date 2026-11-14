import numpy as np

def solve(problem):
    a, b = problem
    n = len(a) + len(b) - 1
    # Choose FFT size: next power of 2 >= n for efficient FFT
    fft_size = 1 << (n - 1).bit_length()
    fa = np.fft.rfft(a, fft_size)
    fb = np.fft.rfft(b, fft_size)
    fc = fa * fb
    result = np.fft.irfft(fc, fft_size)[:n]
    return result