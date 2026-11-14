import numpy as np
from scipy import signal

def solve(problem):
    a, b = problem
    # 确保输入是float64
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    
    n_a = len(a)
    n_b = len(b)
    out_len = n_a + n_b - 1
    
    # 选择FFT大小，2的幂次通常最快
    fft_size = 1
    while fft_size < out_len:
        fft_size *= 2
    
    # FFT卷积
    fa = np.fft.rfft(a, fft_size)
    fb = np.fft.rfft(b, fft_size)
    fc = fa * fb
    result = np.fft.irfft(fc, fft_size)[:out_len]
    
    return result