import numpy as np

def solve(problem):
    a, b = problem
    n = len(a) + len(b) - 1
    # Use FFT for convolution
    fa = np.fft.rfft(a, n=n)
    fb = np.fft.rfft(b, n=n)
    result = np.fft.irfft(fa * fb, n=n)
    return result