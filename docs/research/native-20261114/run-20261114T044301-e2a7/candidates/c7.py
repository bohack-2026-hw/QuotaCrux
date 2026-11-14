import numpy as np
from scipy import signal

def solve(problem):
    a, b = problem
    # Use FFT-based convolution for speed
    result = signal.fftconvolve(a, b, mode='full')
    return result
