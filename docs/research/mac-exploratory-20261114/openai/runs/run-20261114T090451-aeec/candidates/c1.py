from itertools import chain
import numpy as np
from scipy.sparse import csr_matrix


def solve(problem):
    adjacency = problem['adjacency_list']
    n = len(adjacency)
    if n == 0:
        return {'pagerank_scores': []}
    if n == 1:
        return {'pagerank_scores': [1.0]}

    counts = np.fromiter(map(len, adjacency), dtype=np.int64, count=n)
    indptr = np.empty(n + 1, dtype=np.int64)
    indptr[0] = 0
    np.cumsum(counts, out=indptr[1:])
    m = int(indptr[-1])
    indices = np.fromiter(chain.from_iterable(adjacency), dtype=np.int64, count=m)
    matrix = csr_matrix((np.ones(m, dtype=np.float64), indices, indptr), shape=(n, n))
    matrix.sum_duplicates()
    degrees = np.diff(matrix.indptr)
    inverse = np.zeros(n, dtype=np.float64)
    np.divide(1.0, degrees, out=inverse, where=degrees != 0)
    matrix.data = np.repeat(inverse, degrees)
    transition = matrix.transpose()
    dangling = np.flatnonzero(degrees == 0)
    x = np.full(n, 1.0 / n, dtype=np.float64)
    threshold = n * 1e-6
    teleport = 0.15 / n
    for _ in range(100):
        old = x
        x = 0.85 * (transition @ old)
        x += teleport + 0.85 * old[dangling].sum() / n
        if np.abs(x - old).sum() < threshold:
            break
    return {'pagerank_scores': x.tolist()}
