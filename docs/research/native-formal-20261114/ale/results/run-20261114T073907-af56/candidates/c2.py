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
    
    # Find all cells of each color and their adjacencies
    color_cells = {c: [] for c in range(1, m+1)}
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            color_cells[c].append((i,j))
    
    # Build adjacency graph between colors (including 0 for outside)
    adj = {c: set() for c in range(m+1)}  # adj[0] is outside
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check neighbors including outside (boundary)
            if i == 0:
                adj[c].add(0)
                adj[0].add(c)
            if i == n-1:
                adj[c].add(0)
                adj[0].add(c)
            if j == 0:
                adj[c].add(0)
                adj[0].add(c)
            if j == n-1:
                adj[c].add(0)
                adj[0].add(c)
            
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = i+di, j+dj
                if 0 <= ni < n and 0 <= nj < n:
                    nc = grid[ni][nj]
                    if nc != c:
                        adj[c].add(nc)
                        adj[nc].add(c)
    
    # Strategy: Place each color as a small connected blob
    # We need to maintain all adjacencies
    # Simple approach: Try to compress each color into a minimal connected shape
    # while preserving which other colors it touches
    
    # For now, use a simple heuristic: keep the original but try to shrink isolated parts
    # A better approach would be to model this as a constraint satisfaction problem
    
    # Let's try a different strategy: place colors on a smaller grid conceptually
    # But we must fit in n x n
    
    # Simple feasible solution: output the original grid (score = number of 0s + 1)
    # This gives score 1 since there are no 0s in the input (all cells have color 1..m)
    
    # Better: Try to create holes or remove interior cells that don't affect connectivity or adjacency
    
    result = [[0]*n for _ in range(n)]
    
    # First, identify which cells are "essential" for each color
    # A cell is essential if removing it would either:
    # 1. Disconnect the color
    # 2. Remove an adjacency with another color
    
    # Start by marking all cells as potentially removable
    essential = {c: set(color_cells[c]) for c in range(1, m+1)}
    
    # Iteratively remove non-essential cells
    changed = True
    max_iterations = 100
    iteration = 0
    while changed and iteration < max_iterations:
        changed = False
        iteration += 1
        for c in range(1, m+1):
            if not essential[c]:
                continue
            # For each cell, check if it can be removed
            for (i, j) in list(essential[c]):
                # Temporarily remove this cell
                test_essential = essential[c] - {(i,j)}
                if not test_essential:
                    continue
                
                # Check connectivity
                start = next(iter(test_essential))
                visited = {start}
                queue = deque([start])
                while queue:
                    ci, cj = queue.popleft()
                    for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                        ni, nj = ci+di, cj+dj
                        if (ni,nj) in test_essential and (ni,nj) not in visited:
                            visited.add((ni,nj))
                            queue.append((ni,nj))
                if len(visited) != len(test_essential):
                    continue  # Would disconnect
                
                # Check adjacencies: does this cell provide any unique adjacency?
                provides_unique_adj = False
                for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ni, nj = i+di, j+dj
                    if 0 <= ni < n and 0 <= nj < n:
                        nc = grid[ni][nj]
                        if nc != c:
                            # Check if another cell of color c also touches nc
                            has_other_touch = False
                            for (ci, cj) in test_essential:
                                for di2, dj2 in [(-1,0),(1,0),(0,-1),(0,1)]:
                                    ni2, nj2 = ci+di2, cj+dj2
                                    if 0 <= ni2 < n and 0 <= nj2 < n and grid[ni2][nj2] == nc:
                                        has_other_touch = True
                                        break
                                if has_other_touch:
                                    break
                            # Also check boundary for color 0
                            if nc == 0:
                                pass  # Outside is always adjacent if on boundary
                            if not has_other_touch:
                                # Check if it's a boundary cell providing adjacency to 0
                                if nc == 0 and (i==0 or i==n-1 or j==0 or j==n-1):
                                    # Need to check if other cells are also on boundary
                                    other_on_boundary = False
                                    for (ci, cj) in test_essential:
                                        if ci==0 or ci==n-1 or cj==0 or cj==n-1:
                                            other_on_boundary = True
                                            break
                                    if not other_on_boundary:
                                        provides_unique_adj = True
                                else:
                                    provides_unique_adj = True
                    else:
                        # Outside
                        if (i==0 or i==n-1 or j==0 or j==n-1):
                            # This cell touches outside; check if others do too
                            other_on_boundary = False
                            for (ci, cj) in test_essential:
                                if ci==0 or ci==n-1 or cj==0 or cj==n-1:
                                    other_on_boundary = True
                                    break
                            if not other_on_boundary:
                                provides_unique_adj = True
                
                if not provides_unique_adj:
                    essential[c].discard((i,j))
                    changed = True
    
    # Build result grid
    for c in range(1, m+1):
        for (i, j) in essential[c]:
            result[i][j] = c
    
    # Output
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(str(x) for x in result[i]))
    print('\n'.join(out_lines))

solve()