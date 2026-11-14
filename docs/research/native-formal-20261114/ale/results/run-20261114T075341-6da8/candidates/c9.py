import sys
from collections import deque

def solve():
    data = sys.stdin.read().split()
    idx = 0
    n = int(data[idx]); idx += 1
    m = int(data[idx]); idx += 1
    
    grid = []
    for i in range(n):
        row = [int(data[idx+j]) for j in range(n)]
        idx += n
        grid.append(row)
    
    # Build adjacency set: adj[c] = set of colors adjacent to c (including 0)
    adj = [set() for _ in range(m + 1)]
    
    # Boundary adjacencies with color 0
    for i in range(n):
        adj[grid[i][0]].add(0)
        adj[0].add(grid[i][0])
        adj[grid[i][n-1]].add(0)
        adj[0].add(grid[i][n-1])
    for j in range(n):
        adj[grid[0][j]].add(0)
        adj[0].add(grid[0][j])
        adj[grid[n-1][j]].add(0)
        adj[0].add(grid[n-1][j])
    
    # Internal adjacencies
    for i in range(n):
        for j in range(n):
            c1 = grid[i][j]
            if i + 1 < n:
                c2 = grid[i+1][j]
                if c1 != c2:
                    adj[c1].add(c2)
                    adj[c2].add(c1)
            if j + 1 < n:
                c2 = grid[i][j+1]
                if c1 != c2:
                    adj[c1].add(c2)
                    adj[c2].add(c1)
    
    # Start with original grid
    out = [row[:] for row in grid]
    
    def get_cells(color):
        cells = []
        for i in range(n):
            for j in range(n):
                if out[i][j] == color:
                    cells.append((i,j))
        return cells
    
    def is_connected(cells):
        if len(cells) <= 1:
            return True
        cell_set = set(cells)
        start = cells[0]
        visited = {start}
        dq = deque([start])
        while dq:
            ci, cj = dq.popleft()
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = ci+di, cj+dj
                if (ni,nj) in cell_set and (ni,nj) not in visited:
                    visited.add((ni,nj))
                    dq.append((ni,nj))
        return len(visited) == len(cell_set)
    
    def can_remove(i, j):
        c = out[i][j]
        if c == 0:
            return False
        
        # Get neighbors' colors
        neighbor_colors = []
        for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
            ni, nj = i+di, j+dj
            if ni < 0 or ni >= n or nj < 0 or nj >= n:
                neighbor_colors.append(0)
            else:
                neighbor_colors.append(out[ni][nj])
        
        # Check connectivity after removal
        cells_c = get_cells(c)
        remaining = [cell for cell in cells_c if cell != (i,j)]
        if not is_connected(remaining):
            return False
        
        # Check that all required adjacencies are preserved
        for d in set(neighbor_colors):
            if d == c:
                continue
            # Need at least one other pair of c-d adjacent cells
            found = False
            for ci, cj in remaining:
                for di2, dj2 in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ni2, nj2 = ci+di2, cj+dj2
                    nc = 0 if (ni2<0 or ni2>=n or nj2<0 or nj2>=n) else out[ni2][nj2]
                    if nc == d:
                        found = True
                        break
                if found:
                    break
            if not found:
                return False
        
        return True
    
    changed = True
    while changed:
        changed = False
        for i in range(n):
            for j in range(n):
                if out[i][j] != 0 and can_remove(i, j):
                    out[i][j] = 0
                    changed = True
    
    result_lines = [' '.join(map(str, row)) for row in out]
    print('\n'.join(result_lines))

solve()