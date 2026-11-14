from scipy.fft import irfft, next_fast_len, rfft


def solve(problem):
    a, b = problem
    output_length = len(a) + len(b) - 1
    fft_length = next_fast_len(output_length)
    transformed_a = rfft(a, fft_length)
    transformed_b = rfft(b, fft_length)
    return irfft(transformed_a * transformed_b, fft_length)[:output_length]
