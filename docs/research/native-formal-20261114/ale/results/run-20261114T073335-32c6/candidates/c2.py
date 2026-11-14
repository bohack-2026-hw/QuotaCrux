import sys

def solve():
    lines = sys.stdin.read().splitlines()
    n, m = map(int, lines[0].split())
    grid = []
    for i in range(n):
        row = list(map(int, lines[i+1].split()))
        grid.append(row)
    
    # Step 1: Build adjacency graph between colors
    adj = [[False] * (m + 1) for _ in range(m + 1)]
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            if j + 1 < n:
                d = grid[i][j+1]
                adj[c][d] = True
                adj[d][c] = True
            if i + 1 < n:
                d = grid[i+1][j]
                adj[c][d] = True
                adj[d][c] = True
            # Boundary check for color 0
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                adj[c][0] = True
                adj[0][c] = True
    
    # Step 2: For each color, keep only boundary cells (cells that have at least one neighbor of a different color)
    result_grid = [[0] * n for _ in range(n)]
    
    for c in range(1, m + 1):
        for i in range(n):
            for j in range(n):
                if grid[i][j] == c:
                    # Check if this cell is on the boundary of its color region
                    is_boundary = False
                    for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                        ni, nj = i+di, j+dj
                        if 0 <= ni < n and 0 <= nj < n:
                            if grid[ni][nj] != c:
                                is_boundary = True
                                break
                        else:
                            # Outside the grid means adjacent to color 0
                            is_boundary = True
                            break
                    if is_boundary:
                        result_grid[i][j] = c
    
    # Output the result
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(map(str, result_grid[i])))
    print('\n'.join(out_lines))

solve()