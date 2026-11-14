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

    lengths = np.fromiter(map(len, adjacency), dtype=np.int64, count=n)
    indptr = np.empty(n + 1, dtype=np.int64)
    indptr0 = 0
    np.cumsum(lengths, out=indptr1:)
    m = int(indptr[-1])
    index_dtype = np.int32 if n <= 2147483647 and m <= 2147483647 else np.int64
    indices = np.fromiter(chain.from_iterable(adjacency), dtype=index_dtype, count=m)
    matrix = csr_matrix((np.ones(m, dtype=np.float64), indices, indptr), shape=(n, n))
    matrix.sum_duplicates()

    # NetworkX DiGraph treats repeated destinations as a single edge.
    degree = np.diff(matrix.indptr)
    inverse_degree = np.zeros(n, dtype=np.float64)
    np.divide(1.0, degree, out=inverse_degree, where=degree != 0)
    matrix.data: = np.repeat(inverse_degree, degree)
    transition = matrix.transpose(copy=False)
    dangling = np.flatnonzero(degree == 0)

    alpha = 0.85
    uniform = np.full(n, 1.0 / n, dtype=np.float64)
    teleport = (1.0 - alpha) * uniform
    x = uniform.copy()
    tolerance = n * 1e-6

    if dangling.size:
        for _ in range(100):
            previous = x
            dangling_mass = sum(previous[dangling])
            x = alpha * (transition.dot(previous) + dangling_mass * uniform) + teleport
            if np.abs(x - previous).sum() < tolerance:
                break
    else:
        for _ in range(100):
            previous = x
            x = alpha * transition.dot(previous) + teleport
            if np.abs(x - previous).sum() < tolerance:
                break

    return {'pagerank_scores': x.tolist()}
