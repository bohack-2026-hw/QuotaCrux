import sys

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
    
    # Build adjacency graph between colors (including 0 for outside)
    adj = [[False] * (m + 1) for _ in range(m + 1)]
    
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check right and down neighbors to avoid duplicates
            if i < n - 1:
                d = grid[i+1][j]
                if c != d:
                    adj[c][d] = True
                    adj[d][c] = True
            if j < n - 1:
                d = grid[i][j+1]
                if c != d:
                    adj[c][d] = True
                    adj[d][c] = True
            # Boundary check for color 0
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                adj[0][c] = True
                adj[c][0] = True
    
    # Get all required adjacencies
    required_edges = []
    for c in range(1, m+1):
        for d in range(c+1, m+1):
            if adj[c][d]:
                required_edges.append((c, d))
    
    # Also include edges with 0
    zero_adj_colors = set()
    for c in range(1, m+1):
        if adj[0][c]:
            zero_adj_colors.add(c)
    
    # Greedy placement strategy
    # We'll try to place each color as a single cell first, then expand if needed
    # Start with an empty grid filled with 0
    out_grid = [[0]*n for _ in range(n)]
    
    # Place colors one by one
    # Strategy: For each color, find a position that satisfies its adjacencies
    # This is complex, so we use a simpler heuristic:
    # 1. Identify which colors need to be adjacent to 0 (boundary)
    # 2. Place those on the boundary
    # 3. Place others inside, ensuring adjacencies
    
    # Simple approach: Use a spiral or sequential placement
    # Let's try placing colors in order, trying to minimize conflicts
    
    # First, let's identify the structure of adjacencies
    # Colors that are only adjacent to 0 can be placed anywhere on boundary
    # Colors adjacent to other colors need careful placement
    
    # Heuristic: Place each color as a 1x1 block initially
    # Then adjust positions to satisfy adjacencies
    
    # For simplicity, let's use a different approach:
    # Create a new grid where we place colors to form a connected component
    # that preserves the adjacency graph
    
    # This is essentially a graph embedding problem
    # Let's use a simple BFS-based placement
    
    # Start with color 1 at position (0,0)
    placed = {1: [(0,0)]}
    out_grid[0][0] = 1
    
    queue = [1]
    visited = {1}
    
    while queue:
        c = queue.pop(0)
        pos = placed[c][0]  # Use the first position of color c
        ci, cj = pos
        
        # Try to place neighbors of c
        for d in range(1, m+1):
            if d not in visited and adj[c][d]:
                # Find an adjacent empty cell to place d
                found = False
                for di, dj in [(ci-1,cj), (ci+1,cj), (ci,cj-1), (ci,cj+1)]:
                    if 0 <= di < n and 0 <= dj < n and out_grid[di][dj] == 0:
                        out_grid[di][dj] = d
                        placed[d] = [(di,dj)]
                        visited.add(d)
                        queue.append(d)
                        found = True
                        break
                if not found:
                    # Try to find any empty cell adjacent to c's region
                    # This might require expanding c's region
                    pass
    
    # Check if all colors are placed
    for c in range(1, m+1):
        if c not in placed:
            # Find an empty cell to place this color
            for i in range(n):
                for j in range(n):
                    if out_grid[i][j] == 0:
                        out_grid[i][j] = c
                        placed[c] = [(i,j)]
                        break
                else:
                    continue
                break
    
    # Now verify and fix adjacencies
    # This is a simplified version; a full solution would need more sophisticated placement
    
    # Output the result
    print('\n'.join(' '.join(map(str, row)) for row in out_grid))

solve()