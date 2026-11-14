from itertools import chain
import numpy as np
from scipy.sparse import _sparsetools


def solve(problem):
    adjacency = problem['adjacency_list']
    n = len(adjacency)
    if n == 0:
        return {'pagerank_scores': []}
    if n == 1:
        return {'pagerank_scores': [1.0]}

    counts = np.fromiter(map(len, adjacency), dtype=np.int64, count=n)
    m = int(counts.sum())
    if m == 0:
        return {'pagerank_scores': [1.0 / n] * n}
    index_type = np.int32 if max(n, m) < 2147483647 else np.int64
    outgoing_ptr = np.empty(n + 1, dtype=index_type)
    outgoing_ptr[0] = 0
    np.cumsum(counts, out=outgoing_ptr[1:])
    destinations = np.fromiter(chain.from_iterable(adjacency), dtype=index_type, count=m)
    incoming_ptr = np.empty(n + 1, dtype=index_type)
    sources = np.empty(m, dtype=index_type)
    weights = np.empty(m, dtype=np.float64)
    _sparsetools.csr_tocsc(
        n, n, outgoing_ptr, destinations, np.ones(m, dtype=np.float64),
        incoming_ptr, sources, weights
    )
    # Transposition groups incoming edges in increasing source order.
    # Coalescing therefore implements DiGraph's duplicate-edge semantics
    # without sorting each original adjacency row.
    _sparsetools.csr_sum_duplicates(n, n, incoming_ptr, sources, weights)
    used = int(incoming_ptr[-1])
    unique_sources = sources[:used]
    degrees = np.bincount(unique_sources, minlength=n)
    np.divide(0.85, degrees[unique_sources], out=weights[:used])
    dangling = np.flatnonzero(degrees == 0)
    has_dangling = dangling.size != 0
    teleport = 0.15 / n
    threshold = n * 1e-6
    x = np.full(n, 1.0 / n, dtype=np.float64)
    work = np.empty(n, dtype=np.float64)
    for _ in range(100):
        base = teleport
        if has_dangling:
            base += (0.85 / n) * x[dangling].sum()
        work.fill(base)
        _sparsetools.csr_matvec(n, n, incoming_ptr, sources, weights, x, work)
        error = np.abs(work - x).sum()
        x, work = work, x
        if error < threshold:
            break
    return {'pagerank_scores': x.tolist()}
