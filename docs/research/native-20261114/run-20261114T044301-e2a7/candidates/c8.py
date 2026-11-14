import numpy as np
from scipy import signal

def solve(problem):
    a, b = problem
    # Use FFT-based convolution for better performance on large arrays
    return signal.fftconvolve(a, b, mode='full')
