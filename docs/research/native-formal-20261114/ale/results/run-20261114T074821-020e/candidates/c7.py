import sys
from collections import deque

def solve():
    input_data = sys.stdin.read().split()
    idx = 0
    n = int(input_data[idx]); idx += 1
    m = int(input_data[idx]); idx += 1
    
    grid = []
    for i in range(n):
        row = [int(input_data[idx + j]) for j in range(n)]
        idx += n
        grid.append(row)
    
    # Build color adjacency graph
    color_adj = [set() for _ in range(m + 1)]
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
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                color_adj[0].add(c)
                color_adj[c].add(0)
    
    # Use a snake-like path to place colors
    # Create a Hamiltonian path on the grid that visits all cells
    # We'll use a simple serpentine pattern
    path = []
    for i in range(n):
        if i % 2 == 0:
            for j in range(n):
                path.append((i, j))
        else:
            for j in range(n-1, -1, -1):
                path.append((i, j))
    
    # BFS from color 0 to get ordering
    visited = [False] * (m + 1)
    parent = [-1] * (m + 1)
    order = []
    q = deque([0])
    visited[0] = True
    while q:
        u = q.popleft()
        order.append(u)
        for v in sorted(color_adj[u]):
            if not visited[v]:
                visited[v] = True
                parent[v] = u
                q.append(v)
    
    # Place colors along the snake path
    result_grid = [[0] * n for _ in range(n)]
    positions = {}
    
    # Place color 0 at the first position of the path
    pos_idx = 0
    pi, pj = path[pos_idx]
    positions[0] = (pi, pj)
    result_grid[pi][pj] = 0
    pos_idx += 1
    
    success = True
    for color in order:
        if color == 0:
            continue
        p = parent[color]
        pi, pj = positions[p]
        
        # Find an adjacent empty position
        placed = False
        for di, dj in [(0,1), (1,0), (0,-1), (-1,0)]:
            ni, nj = pi + di, pj + dj
            if 0 <= ni < n and 0 <= nj < n and result_grid[ni][nj] == 0 and (ni,nj) not in positions.values():
                result_grid[ni][nj] = color
                positions[color] = (ni, nj)
                placed = True
                break
        
        if not placed:
            # Try to find any empty cell adjacent to parent
            found = False
            for di, dj in [(0,1), (1,0), (0,-1), (-1,0)]:
                ni, nj = pi + di, pj + dj
                if 0 <= ni < n and 0 <= nj < n and result_grid[ni][nj] == 0:
                    # Check if this cell is not used by another color
                    is_used = False
                    for other_color, (oi, oj) in positions.items():
                        if oi == ni and oj == nj:
                            is_used = True
                            break
                    if not is_used:
                        result_grid[ni][nj] = color
                        positions[color] = (ni, nj)
                        found = True
                        break
            if not found:
                success = False
                break
    
    if not success:
        # Fallback: use original grid
        print('\n'.join(' '.join(str(x) for x in row) for row in grid))
        return
    
    # Verify connectivity of each color
    def bfs_color(grid, color, start_i, start_j):
        seen = set()
        q = deque([(start_i, start_j)])
        seen.add((start_i, start_j))
        while q:
            ci, cj = q.popleft()
            for di, dj in [(0,1),(1,0),(0,-1),(-1,0)]:
                ni, nj = ci+di, cj+dj
                if 0 <= ni < n and 0 <= nj < n and (ni,nj) not in seen and grid[ni][nj] == color:
                    seen.add((ni,nj))
                    q.append((ni,nj))
        return len(seen)
    
    for c in range(1, m+1):
        pi, pj = positions[c]
        count = bfs_color(result_grid, c, pi, pj)
        if count != 1:
            print('\n'.join(' '.join(str(x) for x in row) for row in grid))
            return
    
    # Check zero connectivity (including outside)
    zero_count = sum(1 for i in range(n) for j in range(n) if result_grid[i][j] == 0)
    if zero_count > 0:
        zi, zj = -1, -1
        for i in range(n):
            for j in range(n):
                if result_grid[i][j] == 0:
                    zi, zj = i, j
                    break
            if zi >= 0:
                break
        if zi >= 0:
            reached = bfs_color(result_grid, 0, zi, zj)
            if reached != zero_count:
                print('\n'.join(' '.join(str(x) for x in row) for row in grid))
                return
    
    # Check adjacency preservation
    new_adj = [set() for _ in range(m + 1)]
    for i in range(n):
        for j in range(n):
            c = result_grid[i][j]
            if i > 0:
                d = result_grid[i-1][j]
                if c != d:
                    new_adj[c].add(d)
                    new_adj[d].add(c)
            if j > 0:
                d = result_grid[i][j-1]
                if c != d:
                    new_adj[c].add(d)
                    new_adj[d].add(c)
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                new_adj[0].add(c)
                new_adj[c].add(0)
    
    for c in range(m + 1):
        if color_adj[c] != new_adj[c]:
            print('\n'.join(' '.join(str(x) for x in row) for row in grid))
            return
    
    # All checks passed, output result
    print('\n'.join(' '.join(str(x) for x in row) for row in result_grid))

solve()