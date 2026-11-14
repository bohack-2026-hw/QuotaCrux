import sys

def solve():
    input_data = sys.stdin.read().split()
    idx = 0
    n = int(input_data[idx]); idx += 1
    m = int(input_data[idx]); idx += 1
    
    # Read the grid
    grid = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(input_data[idx])); idx += 1
        grid.append(row)
    
    # Find all adjacencies between colors
    adj = set()
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            if i+1 < n and grid[i+1][j] != c:
                pair = (min(c, grid[i+1][j]), max(c, grid[i+1][j]))
                adj.add(pair)
            if j+1 < n and grid[i][j+1] != c:
                pair = (min(c, grid[i][j+1]), max(c, grid[i][j+1]))
                adj.add(pair)
    
    # Also add boundary adjacencies with color 0
    for i in range(n):
        if grid[i][0] != 0:
            adj.add((0, grid[i][0]))
        if grid[i][n-1] != 0:
            adj.add((0, grid[i][n-1]))
    for j in range(n):
        if grid[0][j] != 0:
            adj.add((0, grid[0][j]))
        if grid[n-1][j] != 0:
            adj.add((0, grid[n-1][j]))
    
    # For each color, find its bounding box in the original grid
    color_cells = {c: [] for c in range(1, m+1)}
    for i in range(n):
        for j in range(n):
            color_cells[grid[i][j]].append((i, j))
    
    # Try to place each color as a single cell or small cluster
    # Start by placing each color at a unique position
    # We'll use a greedy approach to minimize 0 cells
    
    # First, let's try to place each color as a single cell
    # Then check if this satisfies all adjacency constraints
    
    # Position assignment: try to pack colors tightly
    positions = {}
    used_positions = set()
    
    # Sort colors by number of neighbors (descending) to place constrained ones first
    color_neighbors = {c: set() for c in range(m+1)}
    for a, b in adj:
        color_neighbors[a].add(b)
        color_neighbors[b].add(a)
    
    sorted_colors = sorted(range(1, m+1), key=lambda c: -len(color_neighbors[c]))
    
    # Place colors one by one, trying to minimize empty space
    # Use a simple heuristic: place near already-placed neighbors
    center = (n//2, n//2)
    
    for c in sorted_colors:
        best_pos = None
        best_score = float('inf')
        
        # Try all available positions
        for i in range(n):
            for j in range(n):
                if (i, j) in used_positions:
                    continue
                
                # Score based on proximity to neighbors
                score = 0
                has_unplaced_neighbor = False
                for nb in color_neighbors[c]:
                    if nb == 0:
                        # Adjacent to boundary - prefer edge positions
                        dist_to_boundary = min(i, j, n-1-i, n-1-j)
                        score += dist_to_boundary * 10
                    elif nb in positions:
                        ni, nj = positions[nb]
                        score += abs(i-ni) + abs(j-nj)
                    else:
                        has_unplaced_neighbor = True
                
                if not has_unplaced_neighbor and score < best_score:
                    best_score = score
                    best_pos = (i, j)
        
        if best_pos is None:
            # Fallback: find any unused position
            for i in range(n):
                for j in range(n):
                    if (i, j) not in used_positions:
                        best_pos = (i, j)
                        break
                if best_pos is not None:
                    break
        
        positions[c] = best_pos
        used_positions.add(best_pos)
    
    # Create the output grid
    out_grid = [[0]*n for _ in range(n)]
    for c, (i, j) in positions.items():
        out_grid[i][j] = c
    
    # Verify the solution
    def verify(grid_out):
        # Check connectivity for each color
        for c in range(1, m+1):
            cells = [(i,j) for i in range(n) for j in range(n) if grid_out[i][j] == c]
            if not cells:
                return False
            # BFS to check connectivity
            visited = set()
            queue = [cells[0]]
            visited.add(cells[0])
            while queue:
                ci, cj = queue.pop(0)
                for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ni, nj = ci+di, cj+dj
                    if 0 <= ni < n and 0 <= nj < n and grid_out[ni][nj] == c and (ni,nj) not in visited:
                        visited.add((ni,nj))
                        queue.append((ni,nj))
            if len(visited) != len(cells):
                return False
        
        # Check adjacency relationships
        out_adj = set()
        for i in range(n):
            for j in range(n):
                c = grid_out[i][j]
                if i+1 < n and grid_out[i+1][j] != c:
                    pair = (min(c, grid_out[i+1][j]), max(c, grid_out[i+1][j]))
                    out_adj.add(pair)
                if j+1 < n and grid_out[i][j+1] != c:
                    pair = (min(c, grid_out[i][j+1]), max(c, grid_out[i][j+1]))
                    out_adj.add(pair)
        for i in range(n):
            if grid_out[i][0] != 0:
                out_adj.add((0, grid_out[i][0]))
            if grid_out[i][n-1] != 0:
                out_adj.add((0, grid_out[i][n-1]))
        for j in range(n):
            if grid_out[0][j] != 0:
                out_adj.add((0, grid_out[0][j]))
            if grid_out[n-1][j] != 0:
                out_adj.add((0, grid_out[n-1][j]))
        
        return out_adj == adj
    
    if not verify(out_grid):
        # Fall back to original grid
        out_grid = grid
    
    # Output
    print('\n'.join(' '.join(map(str, row)) for row in out_grid))

solve()
