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
    
    # Count degrees for each color (excluding color 0)
    degree = [0] * (m + 1)
    for c in range(1, m + 1):
        for d in range(1, m + 1):
            if c != d and adj[c][d]:
                degree[c] += 1
    
    # Sort colors by degree (descending) to place high-degree colors first
    colors_sorted = sorted(range(1, m + 1), key=lambda x: -degree[x])
    
    # Strategy: Place each color as a single cell in a compact arrangement
    # We need to ensure that adjacent colors are placed next to each other
    
    # Create output grid
    out_grid = [[0] * n for _ in range(n)]
    
    # Try to place colors in a space-filling curve pattern
    # First, let's try a simple approach: place all colors as 1x1 blocks
    # in a compact region, then check if the adjacency structure is preserved
    
    # For now, let's implement a basic solution that places colors in a grid pattern
    side = int((m ** 0.5)) + 1
    
    pos = 0
    for c in colors_sorted:
        r = pos // side
        col = pos % side
        # Place at position (r, col) scaled up
        scale = max(1, (n // side))
        rr = min(r * scale, n - 1)
        cc = min(col * scale, n - 1)
        out_grid[rr][cc] = c
        pos += 1
    
    # Fill remaining with 0s (already done)
    
    result_lines = []
    for i in range(n):
        result_lines.append(' '.join(map(str, out_grid[i])))
    print('\n'.join(result_lines))

solve()