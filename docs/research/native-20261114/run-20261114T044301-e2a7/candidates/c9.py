import numpy as np
from scipy import signal

def solve(problem):
    a, b = problem
    return signal.convolve(a, b, mode='full')