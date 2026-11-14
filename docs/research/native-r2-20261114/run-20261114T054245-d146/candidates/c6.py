import numpy as np

def solve(problem):
    a, b = problem
    # 确保输入是float64
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    
    n_a = len(a)
    n_b = len(b)
    n_out = n_a + n_b - 1
    
    # 选择FFT大小，最好是2的幂次以提高效率
    fft_size = 1 << (n_out - 1).bit_length()
    
    # 进行FFT卷积
    fa = np.fft.rfft(a, fft_size)
    fb = np.fft.rfft(b, fft_size)
    fc = fa * fb
    result = np.fft.irfft(fc, fft_size)[:n_out]
    
    return result