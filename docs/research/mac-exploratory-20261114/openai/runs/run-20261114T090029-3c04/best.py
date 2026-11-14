import numpy as np
from scipy.sparse import csr_matrix
from itertools import chain


def solve(problem):
    adj = problem['adjacency_list']
    n = len(adj)
    if n == 0:
        return {'pagerank_scores': []}
    if n == 1:
        return {'pagerank_scores': 1.0}

    lengths = np.fromiter(map(len, adj), dtype=np.int64, count=n)
    indptr = np.empty(n + 1, dtype=np.int64)
    indptr0 = 0
    np.cumsum(lengths, out=indptr1:)
    m = int(indptr[-1])
    indices = np.fromiter(chain.from_iterable(adj), dtype=np.int64, count=m)
    a = csr_matrix((np.ones(m, dtype=np.float64), indices, indptr), shape=(n, n))
    a.sum_duplicates()
    degree = np.diff(a.indptr)
    inv_degree = np.zeros(n, dtype=np.float64)
    np.divide(1.0, degree, out=inv_degree, where=degree != 0)
    a.data: = np.repeat(inv_degree, degree)
    transition = a.transpose().tocsr()
    dangling = np.flatnonzero(degree == 0)
    x = np.full(n, 1.0 / n, dtype=np.float64)
    teleport = (1.0 - 0.85) / n
    tolerance = n * 1.0e-6
    for _ in range(100):
        last = x
        dangling_mass = last[dangling].sum() / n
        x = 0.85 * (transition @ last + dangling_mass) + teleport
        if np.abs(x - last).sum() < tolerance:
            break
    return {'pagerank_scores': x.tolist()}
