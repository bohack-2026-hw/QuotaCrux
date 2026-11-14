# Solver extracted from AlgoTune dff9914c10800c7a031c9e8c3d4d1c8cd1b38906; see UPSTREAM_LICENSE.txt.
# Copyright (c) 2025 Ori Press and the AlgoTune contributors
import numpy as np
from scipy import signal

def solve(problem):
    a, b = problem
    return signal.fftconvolve(a, b, mode='full')
