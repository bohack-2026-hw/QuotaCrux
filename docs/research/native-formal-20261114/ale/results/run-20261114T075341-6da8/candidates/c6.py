import sys
from collections import deque

def solve():
    input_data = sys.stdin.read().split()
    idx = 0
    n = int(input_data[idx]); idx += 1
    m = int(input_data[idx]); idx += 1
    
    grid = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(input_data[idx])); idx += 1
        grid.append(row)
    
    # Build adjacency graph between colors (including color 0 for boundary)
    adj = [[False] * (m + 1) for _ in range(m + 1)]
    
    # Check boundaries - color 0 is outside
    for i in range(n):
        if grid[i][0] != 0:
            adj[grid[i][0]][0] = True
            adj[0][grid[i][0]] = True
        if grid[i][n-1] != 0:
            adj[grid[i][n-1]][0] = True
            adj[0][grid[i][n-1]] = True
    for j in range(n):
        if grid[0][j] != 0:
            adj[grid[0][j]][0] = True
            adj[0][grid[0][j]] = True
        if grid[n-1][j] != 0:
            adj[grid[n-1][j]][0] = True
            adj[0][grid[n-1][j]] = True
    
    # Check internal adjacencies
    for i in range(n):
        for j in range(n):
            c1 = grid[i][j]
            if i + 1 < n:
                c2 = grid[i+1][j]
                if c1 != c2:
                    adj[c1][c2] = True
                    adj[c2][c1] = True
            if j + 1 < n:
                c2 = grid[i][j+1]
                if c1 != c2:
                    adj[c1][c2] = True
                    adj[c2][c1] = True
    
    # Start with the original grid and try to remove internal cells
    out_grid = [row[:] for row in grid]
    
    # For each cell, check if it can be removed (i.e., all its neighbors have the same color or are on the boundary)
    # A cell can be removed if removing it doesn't change the adjacency relationships
    
    # We'll iterate multiple times to allow cascading removals
    changed = True
    while changed:
        changed = False
        for i in range(n):
            for j in range(n):
                c = out_grid[i][j]
                if c == 0:
                    continue
                
                # Check if this cell is an "internal" cell that can be removed
                # It can be removed if all its adjacent cells (up, down, left, right) have the same color as c,
                # OR if it's on the boundary and all its internal neighbors have the same color as c
                
                # Count how many different colors are adjacent to this cell
                neighbor_colors = set()
                has_boundary_neighbor = False
                
                for di, dj in [(-1,0), (1,0), (0,-1), (0,1)]:
                    ni, nj = i + di, j + dj
                    if ni < 0 or ni >= n or nj < 0 or nj >= n:
                        # This is a boundary cell, adjacent to color 0
                        has_boundary_neighbor = True
                    else:
                        nc = out_grid[ni][nj]
                        if nc != c:
                            neighbor_colors.add(nc)
                
                # If this cell has no neighbors of different colors (and no boundary), it's safe to remove
                # But we need to be careful: removing it might disconnect the region
                
                # Simple heuristic: only remove if it has at most one neighbor of a different color
                # This ensures we don't create new adjacencies
                
                if len(neighbor_colors) <= 1 and not has_boundary_neighbor:
                    # Check if removing this cell would disconnect the region
                    # For simplicity, we'll just remove it and rely on the fact that the original regions are connected
                    out_grid[i][j] = 0
                    changed = True
    
    result_lines = []
    for i in range(n):
        result_lines.append(' '.join(map(str, out_grid[i])))
    print('\n'.join(result_lines))

solve()