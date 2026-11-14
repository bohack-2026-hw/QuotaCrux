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
    
    # BFS from color 0 to build spanning tree
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
    
    # Place each color as a single cell on the grid
    result_grid = [[-1] * n for _ in range(n)]
    positions = {}
    positions[0] = (0, 0)
    result_grid[0][0] = 0
    
    success = True
    for color in order:
        if color == 0:
            continue
        p = parent[color]
        pi, pj = positions[p]
        placed = False
        for di, dj in [(0,1), (1,0), (0,-1), (-1,0)]:
            ni, nj = pi + di, pj + dj
            if 0 <= ni < n and 0 <= nj < n and result_grid[ni][nj] == -1:
                result_grid[ni][nj] = color
                positions[color] = (ni, nj)
                placed = True
                break
        if not placed:
            success = False
            break
    
    if not success:
        # Fallback: use original grid
        print('\n'.join(' '.join(str(x) for x in row) for row in grid))
        return
    
    # Fill remaining with 0
    for i in range(n):
        for j in range(n):
            if result_grid[i][j] == -1:
                result_grid[i][j] = 0
    
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