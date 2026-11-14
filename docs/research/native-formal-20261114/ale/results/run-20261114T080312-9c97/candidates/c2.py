import sys
from collections import defaultdict, deque

def solve():
    data = sys.stdin.read().split()
    idx = 0
    n = int(data[idx]); idx += 1
    m = int(data[idx]); idx += 1
    
    grid = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(data[idx])); idx += 1
        grid.append(row)
    
    # Build adjacency graph between colors (including 0 for outside)
    adj = set()  # frozenset of pairs
    color_adj = defaultdict(set)  # color -> set of adjacent colors
    
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check right and down neighbors
            if j + 1 < n:
                d = grid[i][j+1]
                if c != d:
                    pair = frozenset((c, d))
                    adj.add(pair)
                    color_adj[c].add(d)
                    color_adj[d].add(c)
            if i + 1 < n:
                d = grid[i+1][j]
                if c != d:
                    pair = frozenset((c, d))
                    adj.add(pair)
                    color_adj[c].add(d)
                    color_adj[d].add(c)
            # Check boundary for outside (color 0)
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                if c != 0:
                    pair = frozenset((0, c))
                    adj.add(pair)
                    color_adj[0].add(c)
                    color_adj[c].add(0)
    
    # Determine which colors touch the boundary
    boundary_colors = set()
    for i in range(n):
        for j in range(n):
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                boundary_colors.add(grid[i][j])
    
    # Strategy: Place each color as a single cell where possible.
    # We need to arrange cells so that adjacent colors share edges.
    # Colors touching boundary must be on the boundary.
    
    # Let's try a simple approach: place colors in a grid pattern
    # First, separate boundary and non-boundary colors
    boundary_list = [c for c in range(1, m+1) if c in boundary_colors]
    interior_list = [c for c in range(1, m+1) if c not in boundary_colors]
    
    # For now, use a heuristic placement
    # Place boundary colors along the perimeter, interior colors inside
    
    result = [[0]*n for _ in range(n)]
    
    # Simple approach: just output original grid (same as c0) but let's try something better
    # Actually, let's try to pack colors more tightly
    
    # A better approach: treat this as a graph embedding problem
    # Each color needs at least 1 cell. Adjacent colors need to share an edge.
    
    # Let's try placing each color as one cell in a compact arrangement
    # Start with a center position and expand outward
    
    # Use BFS-like placement from a central color
    all_colors = list(range(1, m+1))
    
    # Find a good starting color (one with many connections)
    if all_colors:
        start_color = max(all_colors, key=lambda c: len(color_adj.get(c, set())))
    else:
        start_color = 1
    
    placed = {start_color}
    positions = {}  # color -> (i, j)
    
    # Place start color in center
    ci, cj = n//2, n//2
    positions[start_color] = (ci, cj)
    result[ci][cj] = start_color
    
    # BFS to place other colors
    queue = deque([start_color])
    while queue:
        cur = queue.popleft()
        ci, cj = positions[cur]
        
        # Try to place neighbors in available adjacent cells
        neighbors = list(color_adj.get(cur, set()))
        random.shuffle(neighbors)  # Add randomness for variety
        
        for nb in neighbors:
            if nb in placed or nb == 0:
                continue
            
            # Try to find an empty cell adjacent to cur's position
            found = False
            for di, dj in [(0,1),(0,-1),(1,0),(-1,0)]:
                ni, nj = ci+di, cj+dj
                if 0 <= ni < n and 0 <= nj < n and result[ni][nj] == 0:
                    result[ni][nj] = nb
                    positions[nb] = (ni, nj)
                    placed.add(nb)
                    queue.append(nb)
                    found = True
                    break
            
            if not found:
                # Need to create space - skip for now, will handle later
                pass
    
    # Handle remaining unplaced colors
    for c in all_colors:
        if c not in placed:
            # Find any empty cell
            placed_anywhere = False
            for i in range(n):
                for j in range(n):
                    if result[i][j] == 0:
                        result[i][j] = c
                        positions[c] = (i, j)
                        placed.add(c)
                        placed_anywhere = True
                        break
                if placed_anywhere:
                    break
            
            if not placed_anywhere:
                # Grid is full - shouldn't happen since m << n*n
                pass
    
    # Now we have a basic layout. But we need to verify adjacency constraints.
    # This simple approach may not satisfy all adjacency requirements.
    # For a more robust solution, we'd need to verify and fix violations.
    
    # For now, let's just output this and see how it scores
    print('\n'.join(' '.join(map(str, row)) for row in result))

solve()
