import numpy as np
from scipy import signal

def solve(problem):
    a, b = problem
    return signal.fftconvolve(a, b, mode='full')