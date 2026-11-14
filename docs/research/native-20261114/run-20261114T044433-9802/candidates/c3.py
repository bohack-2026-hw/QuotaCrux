# Solver extracted from AlgoTune dff9914c10800c7a031c9e8c3d4d1c8cd1b38906; see UPSTREAM_LICENSE.txt.
# Copyright (c) 2025 Ori Press and the AlgoTune contributors
import numpy as np

def solve(problem):
    a, b = problem
    n = len(a) + len(b) - 1
    # Find next power of 2 for efficient FFT
    fft_size = 1 << (n - 1).bit_length()
    fa = np.fft.rfft(a, fft_size)
    fb = np.fft.rfft(b, fft_size)
    fc = fa * fb
    result = np.fft.irfft(fc, fft_size)[:n]
    return result
