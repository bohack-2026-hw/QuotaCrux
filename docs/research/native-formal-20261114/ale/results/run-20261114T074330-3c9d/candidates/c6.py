import sys
from collections import deque

def solve():
    data = sys.stdin.read().split()
    n = int(data[0])
    m = int(data[1])
    grid = []
    idx = 2
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(data[idx]))
            idx += 1
        grid.append(row)
    
    # Find adjacency between colors
    adj = [[False] * (m + 1) for _ in range(m + 1)]
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check boundary (adjacent to 0)
            if i == 0 or i == n - 1 or j == 0 or j == n - 1:
                adj[c][0] = True
                adj[0][c] = True
            # Check right and down neighbors
            if j + 1 < n:
                d = grid[i][j + 1]
                if c != d:
                    adj[c][d] = True
                    adj[d][c] = True
            if i + 1 < n:
                d = grid[i + 1][j]
                if c != d:
                    adj[c][d] = True
                    adj[d][c] = True
    
    # For each color, find a compact representation
    # Strategy: place each color as a small connected blob
    # We need to ensure that if two colors are adjacent, their blobs touch
    
    # First, let's figure out which colors need to be on the boundary
    boundary_colors = set()
    for c in range(1, m + 1):
        if adj[c][0]:
            boundary_colors.add(c)
    
    # Build adjacency graph among non-zero colors
    color_adj = {c: set() for c in range(1, m + 1)}
    for c in range(1, m + 1):
        for d in range(1, m + 1):
            if c < d and adj[c][d]:
                color_adj[c].add(d)
                color_adj[d].add(c)
    
    # Greedy placement strategy:
    # Place colors one by one, trying to fit them into existing space
    # Start with boundary colors, then interior colors
    
    # Create output grid initialized to 0
    out = [[0] * n for _ in range(n)]
    
    # Track used positions
    used = [[False] * n for _ in range(n)]
    
    # For each color, we'll try to place it in a compact shape
    # Start with colors that have the most connections first
    
    # Sort colors by number of adjacencies (descending)
    colors_sorted = sorted(range(1, m + 1), key=lambda c: len(color_adj[c]), reverse=True)
    
    # Position tracking for each color
    color_pos = {}  # color -> list of (i,j)
    
    def can_place(i, j, c):
        """Check if we can place color c at position (i,j) without violating constraints"""
        if i < 0 or i >= n or j < 0 or j >= n:
            return False
        if used[i][j]:
            return False
        # Check if this would create unwanted adjacency
        for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
            ni, nj = i+di, j+dj
            if 0 <= ni < n and 0 <= nj < n:
                if out[ni][nj] != 0 and out[ni][nj] != c:
                    other = out[ni][nj]
                    if not adj[c][other]:
                        return False
        return True
    
    def try_place_color(c, start_i=None, start_j=None):
        """Try to place color c starting from a given position"""
        placed = []
        
        # BFS to find a compact region
        if start_i is not None and start_j is not None:
            queue = deque([(start_i, start_j)])
            visited = set()
            while queue and len(placed) < 5:  # Limit size for compactness
                i, j = queue.popleft()
                if (i, j) in visited:
                    continue
                if not can_place(i, j, c):
                    continue
                visited.add((i, j))
                placed.append((i, j))
                for di, dj in [(0,1),(1,0),(0,-1),(-1,0)]:
                    ni, nj = i+di, j+dj
                    if 0 <= ni < n and 0 <= nj < n and (ni,nj) not in visited:
                        queue.append((ni, nj))
        else:
            # Try all possible starting positions
            best_placement = None
            best_score = -1
            for si in range(n):
                for sj in range(n):
                    if not can_place(si, sj, c):
                        continue
                    # Try placing here
                    test_placed = []
                    queue = deque([(si, sj)])
                    visited = set()
                    while queue and len(test_placed) < 5:
                        i, j = queue.popleft()
                        if (i, j) in visited:
                            continue
                        if not can_place(i, j, c):
                            continue
                        visited.add((i, j))
                        test_placed.append((i, j))
                        for di, dj in [(0,1),(1,0),(0,-1),(-1,0)]:
                            ni, nj = i+di, j+dj
                            if 0 <= ni < n and 0 <= nj < n and (ni,nj) not in visited:
                                queue.append((ni, nj))
                    
                    # Score based on how many required adjacencies this satisfies
                    score = 0
                    for pi, pj in test_placed:
                        for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                            ni, nj = pi+di, pj+dj
                            if 0 <= ni < n and 0 <= nj < n:
                                if out[ni][nj] != 0 and out[ni][nj] != c:
                                    other = out[ni][nj]
                                    if adj[c][other]:
                                        score += 1
                    
                    if score > best_score:
                        best_score = score
                        best_placement = test_placed
                    
                    if len(test_placed) >= 3:  # Good enough
                        break
                if best_placement and len(best_placement) >= 3:
                    break
            
            if best_placement:
                placed = best_placement
            else:
                # Fallback: just place one cell
                for si in range(n):
                    for sj in range(n):
                        if can_place(si, sj, c):
                            placed = [(si, sj)]
                            break
                    if placed:
                        break
        
        if not placed:
            return False
        
        # Commit the placement
        for i, j in placed:
            out[i][j] = c
            used[i][j] = True
        color_pos[c] = placed
        return True
    
    # Place colors in order of connectivity
    for c in colors_sorted:
        if not try_place_color(c):
            # If we couldn't place it properly, try harder
            pass
    
    # Verify and fix any issues
    # Count zeros
    zero_count = sum(1 for i in range(n) for j in range(n) if out[i][j] == 0)
    
    print(zero_count + 1)
    for i in range(n):
        print(' '.join(map(str, out[i])))

solve()
