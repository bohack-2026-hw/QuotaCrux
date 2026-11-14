import numpy as np

def solve(problem):
    a, b = problem
    n = len(a) + len(b) - 1
    m = 1 << (n - 1).bit_length()
    fa = np.fft.rfft(a, m)
    fb = np.fft.rfft(b, m)
    return np.fft.irfft(fa * fb, m)[:n]