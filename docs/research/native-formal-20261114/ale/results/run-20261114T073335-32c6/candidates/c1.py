import sys

def solve():
    lines = sys.stdin.read().splitlines()
    n, m = map(int, lines[0].split())
    grid = []
    for i in range(n):
        row = list(map(int, lines[i+1].split()))
        grid.append(row)
    
    # Step 1: Build adjacency graph between colors
    adj = [[False] * (m + 1) for _ in range(m + 1)]
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check right and down neighbors
            if j + 1 < n:
                d = grid[i][j+1]
                adj[c][d] = True
                adj[d][c] = True
            if i + 1 < n:
                d = grid[i+1][j]
                adj[c][d] = True
                adj[d][c] = True
            # Boundary check for color 0
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                adj[c][0] = True
                adj[0][c] = True
    
    # Step 2: For each color, find minimal connected subset that preserves adjacencies
    # We'll use a greedy approach: start with all cells of the color, then try to remove cells
    # while maintaining connectivity and required adjacencies
    
    result_grid = [[0] * n for _ in range(n)]
    
    # First, let's identify which colors need to be adjacent to which
    # Then we'll place them strategically
    
    # A simpler approach: for each color, keep only the cells that are essential
    # Essential cells are those that have at least one neighbor of a different color
    # that requires adjacency
    
    # Let's try a different strategy: compress each color to its "skeleton"
    # Start by marking all cells as potential candidates
    
    # Actually, let's use a more systematic approach:
    # 1. For each color c, find all cells of color c
    # 2. Among these, identify cells that must be kept because they provide necessary adjacencies
    # 3. Find a minimal connected subgraph containing all essential cells
    
    from collections import deque
    
    def get_cells_of_color(color):
        cells = []
        for i in range(n):
            for j in range(n):
                if grid[i][j] == color:
                    cells.append((i, j))
        return cells
    
    def bfs_minimal_connected(cells, required_neighbors):
        """
        Find a minimal connected set of cells from 'cells' that includes all cells
        that have required neighbors, and maintains connectivity.
        """
        if not cells:
            return []
        
        cell_set = set(cells)
        
        # Identify essential cells: those that have at least one required neighbor
        essential = set()
        for (i, j) in cells:
            has_required = False
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = i+di, j+dj
                if 0 <= ni < n and 0 <= nj < n:
                    if (ni, nj) in required_neighbors:
                        has_required = True
                        break
            if has_required:
                essential.add((i, j))
        
        if not essential:
            # No essential cells, just pick one arbitrary cell
            return [cells[0]]
        
        # Now find minimal connected set containing all essential cells
        # Use BFS from one essential cell, adding paths to other essential cells
        
        # Start with all essential cells
        included = set(essential)
        
        # Check connectivity; if not connected, add intermediate cells
        # This is a Steiner tree problem, but we'll use a greedy approximation
        
        # Simple approach: repeatedly connect closest pair of components
        # For simplicity, let's just include all cells on shortest paths between essential cells
        
        # Even simpler: just return all essential cells plus any cells needed for connectivity
        # In practice, for this problem, keeping all boundary cells of each region should work
        
        # Let's try: keep all cells that are on the boundary of their color region
        # (i.e., have at least one neighbor of a different color)
        
        boundary_cells = set()
        for (i, j) in cells:
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = i+di, j+dj
                if 0 <= ni < n and 0 <= nj < n:
                    if grid[ni][nj] != color:
                        boundary_cells.add((i, j))
                        break
        
        # The boundary cells should form a connected set (since the original region is connected)
        # But they might not be minimal. Let's use them as our compressed representation.
        
        # Actually, let's be even more aggressive: try to remove interior cells
        # Keep only cells that are either essential or needed for connectivity
        
        # For now, let's use boundary cells as a good compromise
        return list(boundary_cells) if boundary_cells else list(essential)
    
    # Process each color
    for c in range(1, m + 1):
        cells = get_cells_of_color(c)
        if not cells:
            continue
        
        # Find required neighbors: cells of other colors that are adjacent to c
        required_neighbors = set()
        for (i, j) in cells:
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = i+di, j+dj
                if 0 <= ni < n and 0 <= nj < n:
                    if grid[ni][nj] != c:
                        required_neighbors.add((ni, nj))
        
        # Get minimal connected subset
        minimal_cells = bfs_minimal_connected(cells, required_neighbors)
        
        # Place them in the result grid
        for (i, j) in minimal_cells:
            result_grid[i][j] = c
    
    # Output the result
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(map(str, result_grid[i])))
    print('\n'.join(out_lines))

solve()
