# Solver extracted from AlgoTune dff9914c10800c7a031c9e8c3d4d1c8cd1b38906; see UPSTREAM_LICENSE.txt.
# Copyright (c) 2025 Ori Press and the AlgoTune contributors
import logging
import numpy as np
from scipy import signal

class Convolve1D(object):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mode = 'full'

    def solve(self, problem: tuple) -> np.ndarray:
        a, b = problem
        return signal.fftconvolve(a, b, mode=self.mode)

def solve(problem):
    return Convolve1D().solve(problem)
