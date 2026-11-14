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
    
    # Compute adjacency between colors in original map
    adj = [[False] * (m + 1) for _ in range(m + 1)]
    
    def get_neighbors(i, j):
        """Get neighbors including outside (color 0)"""
        neighbors = []
        if i == 0:
            neighbors.append(0)
        else:
            neighbors.append(grid[i-1][j])
        if i == n-1:
            neighbors.append(0)
        else:
            neighbors.append(grid[i+1][j])
        if j == 0:
            neighbors.append(0)
        else:
            neighbors.append(grid[i][j-1])
        if j == n-1:
            neighbors.append(0)
        else:
            neighbors.append(grid[i][j+1])
        return neighbors
    
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            for nb in get_neighbors(i, j):
                if c != nb:
                    adj[c][nb] = True
                    adj[nb][c] = True
    
    # For each color, find all cells and try to shrink them
    # Strategy: iteratively remove boundary cells that don't break connectivity
    # or adjacency requirements
    
    # First, let's create a new grid where we'll place shrunk versions
    # We need to figure out positions for each color
    
    # Approach: Use a greedy packing approach
    # Place each color as a compact block, ensuring adjacencies are preserved
    
    # Let's think differently: start with the original grid and try to remove cells
    # from the periphery while maintaining validity
    
    # A simpler approach: for each color, compute its bounding box and try to
    # shrink it towards the center while maintaining connectivity and adjacencies
    
    # Actually, let's use a different strategy:
    # 1. Identify which colors are on the boundary (adjacent to 0)
    # 2. Try to pack all colors into a smaller region
    
    # Let me implement a simple but effective heuristic:
    # For each color, find a minimal connected subgraph that preserves all adjacencies
    
    # Step 1: For each color c, determine which other colors it must be adjacent to
    required_adj = {}
    for c in range(1, m+1):
        required_adj[c] = set()
        for d in range(m+1):
            if c != d and adj[c][d]:
                required_adj[c].add(d)
    
    # Step 2: For each color, find cells that are "essential" for maintaining adjacency
    # A cell of color c is essential if removing it would break an adjacency with some color d
    
    # This is complex. Let me try a simpler iterative removal approach.
    
    # New grid starts as copy of original
    new_grid = [row[:] for row in grid]
    
    # Iteratively try to remove cells from the boundary
    # A cell can be removed if:
    # 1. It's on the outer boundary of its color's region
    # 2. Removing it doesn't disconnect the color's region
    # 3. Removing it doesn't break any required adjacency
    
    # Let's implement this carefully
    
    # For efficiency, let's process colors one by one
    # For each color, find removable cells and remove them
    
    def is_connected(cells):
        """Check if a set of cells forms a connected component"""
        if not cells:
            return True
        cell_set = set(cells)
        start = next(iter(cell_set))
        visited = {start}
        queue = deque([start])
        while queue:
            i, j = queue.popleft()
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = i+di, j+dj
                if (ni, nj) in cell_set and (ni, nj) not in visited:
                    visited.add((ni, nj))
                    queue.append((ni, nj))
        return len(visited) == len(cell_set)
    
    # Get all cells for each color
    color_cells = {c: [] for c in range(1, m+1)}
    for i in range(n):
        for j in range(n):
            c = new_grid[i][j]
            color_cells[c].append((i, j))
    
    # For each color, iteratively try to remove boundary cells
    # We do multiple passes to allow cascading removals
    
    for iteration in range(50):  # Limit iterations
        changed = False
        for c in range(1, m+1):
            cells = color_cells[c]
            if not cells:
                continue
            
            cell_set = set(cells)
            
            # Find boundary cells (cells with at least one neighbor not in same color)
            boundary_cells = []
            for (i, j) in cells:
                is_boundary = False
                for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ni, nj = i+di, j+dj
                    if ni < 0 or ni >= n or nj < 0 or nj >= n:
                        is_boundary = True
                        break
                    if new_grid[ni][nj] != c:
                        is_boundary = True
                        break
                if is_boundary:
                    boundary_cells.append((i, j))
            
            # Try to remove each boundary cell
            for (i, j) in boundary_cells:
                if (i, j) not in cell_set:
                    continue
                
                # Check if removing this cell breaks connectivity
                remaining = cell_set - {(i, j)}
                if not is_connected(list(remaining)):
                    continue
                
                # Check if removing this cell breaks any required adjacency
                # The cell (i,j) has neighbors of various colors
                # If this is the ONLY cell of color c adjacent to some color d,
                # then we can't remove it
                
                # Find all colors that this cell is adjacent to
                adjacent_colors = set()
                for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ni, nj = i+di, j+dj
                    if ni < 0 or ni >= n or nj < 0 or nj >= n:
                        adjacent_colors.add(0)
                    else:
                        adjacent_colors.add(new_grid[ni][nj])
                adjacent_colors.discard(c)
                
                # For each adjacent color, check if there are other cells of color c
                # that are also adjacent to that color
                can_remove = True
                for d in adjacent_colors:
                    if d == 0:
                        # Adjacent to outside - check if other cells of c are also on boundary
                        # Actually, we need at least one cell of c to be adjacent to 0
                        # if c was originally adjacent to 0
                        if 0 in required_adj[c]:
                            # Check if any other cell of c is adjacent to outside
                            found_other = False
                            for (ci, cj) in remaining:
                                for di2, dj2 in [(-1,0),(1,0),(0,-1),(0,1)]:
                                    ni2, nj2 = ci+di2, cj+dj2
                                    if ni2 < 0 or ni2 >= n or nj2 < 0 or nj2 >= n:
                                        found_other = True
                                        break
                                    if new_grid[ni2][nj2] == 0:
                                        found_other = True
                                        break
                                if found_other:
                                    break
                            if not found_other:
                                can_remove = False
                                break
                    else:
                        # Adjacent to color d - check if other cells of c are adjacent to d
                        if d in required_adj[c]:
                            found_other = False
                            for (ci, cj) in remaining:
                                for di2, dj2 in [(-1,0),(1,0),(0,-1),(0,1)]:
                                    ni2, nj2 = ci+di2, cj+dj2
                                    if 0 <= ni2 < n and 0 <= nj2 < n and new_grid[ni2][nj2] == d:
                                        found_other = True
                                        break
                                    elif ni2 < 0 or ni2 >= n or nj2 < 0 or nj2 >= n:
                                        # Outside, not d unless d==0
                                        pass
                                if found_other:
                                    break
                            if not found_other:
                                can_remove = False
                                break
                
                if can_remove:
                    # Remove this cell
                    new_grid[i][j] = 0
                    cell_set.remove((i, j))
                    color_cells[c] = list(cell_set)
                    changed = True
        
        if not changed:
            break
    
    # Output the result
    output_lines = []
    for i in range(n):
        output_lines.append(' '.join(map(str, new_grid[i])))
    print('\n'.join(output_lines))

solve()
