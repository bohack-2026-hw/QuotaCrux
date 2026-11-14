# Solver extracted from AlgoTune dff9914c10800c7a031c9e8c3d4d1c8cd1b38906; see UPSTREAM_LICENSE.txt.
# Copyright (c) 2025 Ori Press and the AlgoTune contributors
import logging
import math
import random
from typing import Any
import networkx as nx
import numpy as np
RTOL = 1e-05
ATOL = 1e-08

class PageRankTask(object):

    def __init__(self, **kwargs):
        """
        Initialize the PageRankTask.
        """
        super().__init__(**kwargs)
        self.alpha = 0.85
        self.max_iter = 100
        self.tol = 1e-06

    def solve(self, problem: dict[str, list[list[int]]]) -> dict[str, list[float]]:
        """
        Calculates the PageRank scores for the graph using NetworkX.

        Args:
            problem: A dictionary containing the adjacency list of the graph.
                     {"adjacency_list": adj_list}

        Returns:
            A dictionary containing the PageRank scores as a list, ordered by node index.
            {"pagerank_scores": [score_node_0, score_node_1, ..., score_node_n-1]}
            Returns {"pagerank_scores": []} for n=0.
            Returns {"pagerank_scores": 1.0} for n=1.
        """
        adj_list = problem['adjacency_list']
        n = len(adj_list)
        if n == 0:
            return {'pagerank_scores': []}
        if n == 1:
            return {'pagerank_scores': 1.0}
        G = nx.DiGraph()
        G.add_nodes_from(range(n))
        for u, neighbors in enumerate(adj_list):
            for v in neighbors:
                G.add_edge(u, v)
        try:
            pagerank_dict = nx.pagerank(G, alpha=self.alpha, max_iter=self.max_iter, tol=self.tol)
            pagerank_list = 0.0 * n
            for node, score in pagerank_dict.items():
                if 0 <= node < n:
                    pagerank_list[node] = float(score)
                else:
                    logging.warning(f'PageRank returned score for unexpected node {node}')
        except nx.PowerIterationFailedConvergence:
            logging.error(f'networkx.pagerank failed to converge after {self.max_iter} iterations.')
            pagerank_list = 0.0 * n
        except Exception as e:
            logging.error(f'networkx.pagerank failed with an unexpected error: {e}')
            pagerank_list = 0.0 * n
        solution = {'pagerank_scores': pagerank_list}
        return solution

def solve(problem):
    return PageRankTask().solve(problem)
