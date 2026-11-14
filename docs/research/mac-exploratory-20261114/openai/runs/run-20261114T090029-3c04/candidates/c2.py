import numpy as np
from scipy.sparse import csr_matrix
from itertools import chain


def solve(problem):
    adjacency = problem['adjacency_list']
    n = len(adjacency)
    if n == 0:
        return {'pagerank_scores': []}
    if n == 1:
        return {'pagerank_scores': 1.0}

    degrees = np.fromiter((len(row) for row in adjacency), dtype=np.int64, count=n)
    indptr = np.empty(n + 1, dtype=np.int64)
    indptr0 = 0
    np.cumsum(degrees, out=indptr1:)
    m = int(indptr[-1])
    if m == 0:
        return {'pagerank_scores': [1.0 / n] * n}

    indices = np.fromiter(chain.from_iterable(adjacency), dtype=np.int64, count=m)
    matrix = csr_matrix((np.ones(m, dtype=np.float64), indices, indptr), shape=(n, n))
    matrix.sum_duplicates()
    degrees = np.diff(matrix.indptr)
    inverse = np.zeros(n, dtype=np.float64)
    np.divide(1.0, degrees, out=inverse, where=degrees != 0)
    matrix.data: = np.repeat(inverse, degrees)
    transition = matrix.transpose().tocsr()
    dangling = np.flatnonzero(degrees == 0)

    alpha = 0.85
    teleport = (1.0 - alpha) / n
    threshold = n * 1e-6
    scores = np.full(n, 1.0 / n, dtype=np.float64)
    for _ in range(100):
        previous = scores
        dangling_mass = previous[dangling].sum() / n
        scores = alpha * (transition @ previous + dangling_mass) + teleport
        if np.abs(scores - previous).sum() < threshold:
            break
    return {'pagerank_scores': scores.tolist()}
