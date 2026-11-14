from itertools import chain
import numpy as np
from scipy.sparse import _sparsetools


def solve(problem):
    adjacency = problem['adjacency_list']
    n = len(adjacency)
    if n == 0:
        return {'pagerank_scores': []}
    if n == 1:
        return {'pagerank_scores': 1.0}

    counts = np.fromiter(map(len, adjacency), dtype=np.int64, count=n)
    indptr = np.empty(n + 1, dtype=np.int64)
    indptr0 = 0
    np.cumsum(counts, out=indptr1:)
    m = int(indptr[-1])
    indices = np.fromiter(chain.from_iterable(adjacency), dtype=np.int64, count=m)
    data = np.ones(m, dtype=np.float64)
    _sparsetools.csr_sort_indices(n, indptr, indices, data)
    _sparsetools.csr_sum_duplicates(n, n, indptr, indices, data)
    degrees = np.diff(indptr)
    scale = np.zeros(n, dtype=np.float64)
    np.divide(0.85, degrees, out=scale, where=degrees != 0)
    data = np.repeat(scale, degrees)
    dangling = np.flatnonzero(degrees == 0)
    has_dangling = dangling.size != 0
    x = np.full(n, 1.0 / n, dtype=np.float64)
    work = np.empty(n, dtype=np.float64)
    teleport = 0.15 / n
    threshold = n * 1e-6
    for _ in range(100):
        base = teleport
        if has_dangling:
            base += (0.85 / n) * x[dangling].sum()
        work.fill(base)
        _sparsetools.csc_matvec(n, n, indptr, indices, data, x, work)
        error = np.abs(work - x).sum()
        x, work = work, x
        if error < threshold:
            break
    return {'pagerank_scores': x.tolist()}
