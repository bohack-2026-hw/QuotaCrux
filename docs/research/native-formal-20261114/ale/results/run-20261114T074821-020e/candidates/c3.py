import sys
from collections import deque

def solve():
    input_data = sys.stdin.read().split()
    idx = 0
    n = int(input_data[idx]); idx += 1
    m = int(input_data[idx]); idx += 1
    
    # Read the grid
    grid = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(input_data[idx]))
            idx += 1
        grid.append(row)
    
    # Build adjacency relationships between colors
    color_adj = {c: set() for c in range(m + 1)}
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            if i > 0:
                d = grid[i-1][j]
                if c != d:
                    color_adj[c].add(d)
                    color_adj[d].add(c)
            if j > 0:
                d = grid[i][j-1]
                if c != d:
                    color_adj[c].add(d)
                    color_adj[d].add(c)
            # Boundary cells are adjacent to color 0 (outside)
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                if c != 0:
                    color_adj[0].add(c)
                    color_adj[c].add(0)
    
    # Find a spanning tree of the dual graph to determine placement order
    visited = [False] * (m + 1)
    parent = [-1] * (m + 1)
    order = []
    
    def dfs(color):
        visited[color] = True
        order.append(color)
        for neighbor in sorted(color_adj[color]):
            if not visited[neighbor]:
                parent[neighbor] = color
                dfs(neighbor)
    
    dfs(0)
    
    # Create a new grid where each color occupies exactly one cell arranged according to the DFS tree
    result_grid = [[-1] * n for _ in range(n)]
    positions = {}
    
    # Start with color 0 at position (0,0)
    positions[0] = (0, 0)
    result_grid[0][0] = 0
    
    # Place other colors adjacent to their parents
    for color in order:
        if color == 0:
            continue
        p = parent[color]
        pi, pj = positions[p]
        # Try to find an adjacent empty position
        placed = False
        for di, dj in [(0,1), (1,0), (0,-1), (-1,0)]:
            ni, nj = pi + di, pj + dj
            if 0 <= ni < n and 0 <= nj < n and result_grid[ni][nj] == -1:
                result_grid[ni][nj] = color
                positions[color] = (ni, nj)
                placed = True
                break
        if not placed:
            # This shouldn't happen with proper planning, but handle gracefully
            pass
    
    # Fill remaining -1 with 0
    for i in range(n):
        for j in range(n):
            if result_grid[i][j] == -1:
                result_grid[i][j] = 0
    
    # Output the result
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(str(x) for x in result_grid[i]))
    print('\n'.join(out_lines))

solve()