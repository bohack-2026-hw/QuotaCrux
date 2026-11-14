import sys
from collections import deque

def solve():
    lines = sys.stdin.read().splitlines()
    n, m = map(int, lines[0].split())
    grid = []
    for i in range(n):
        row = list(map(int, lines[i+1].split()))
        grid.append(row)
    
    # Step 1: Build adjacency matrix between colors
    adj = [[False] * (m + 1) for _ in range(m + 1)]
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
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
    result_grid = [[0] * n for _ in range(n)]
    
    def get_cells_of_color(color):
        cells = []
        for i in range(n):
            for j in range(n):
                if grid[i][j] == color:
                    cells.append((i, j))
        return cells
    
    def is_connected(cells_set):
        """Check if a set of cells is connected."""
        if not cells_set:
            return True
        start = next(iter(cells_set))
        visited = {start}
        queue = deque([start])
        while queue:
            ci, cj = queue.popleft()
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = ci+di, cj+dj
                if (ni, nj) in cells_set and (ni, nj) not in visited:
                    visited.add((ni, nj))
                    queue.append((ni, nj))
        return len(visited) == len(cells_set)
    
    def find_minimal_connected(cells, required_adj_colors):
        """
        Find a minimal connected subset of 'cells' that maintains adjacency with all required colors.
        Strategy: keep boundary cells, ensure connectivity.
        """
        cell_set = set(cells)
        
        # Identify essential cells: those adjacent to required colors
        essential = set()
        for (i, j) in cells:
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = i+di, j+dj
                if 0 <= ni < n and 0 <= nj < n:
                    neighbor_color = grid[ni][nj]
                    if neighbor_color in required_adj_colors:
                        essential.add((i, j))
                        break
                else:
                    # Outside the grid means adjacent to color 0
                    if 0 in required_adj_colors:
                        essential.add((i, j))
                        break
        
        if not essential:
            # No essential cells, just pick one arbitrary cell
            return [cells[0]]
        
        # Start with essential cells
        included = set(essential)
        
        # Check if essential cells are connected; if not, add paths between them
        # Use BFS to connect components
        
        # First, find connected components of essential cells
        components = []
        unvisited = set(essential)
        while unvisited:
            comp = set()
            start = next(iter(unvisited))
            queue = deque([start])
            comp.add(start)
            unvisited.remove(start)
            while queue:
                ci, cj = queue.popleft()
                for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ni, nj = ci+di, cj+dj
                    if (ni, nj) in unvisited:
                        unvisited.remove((ni, nj))
                        comp.add((ni, nj))
                        queue.append((ni, nj))
            components.append(comp)
        
        # If multiple components, we need to connect them using cells from 'cells'
        # Greedy: repeatedly connect closest pair of components
        while len(components) > 1:
            # Find closest pair of components
            min_dist = float('inf')
            best_pair = None
            for idx1 in range(len(components)):
                for idx2 in range(idx1+1, len(components)):
                    for c1 in components[idx1]:
                        for c2 in components[idx2]:
                            dist = abs(c1[0]-c2[0]) + abs(c1[1]-c2[1])
                            if dist < min_dist:
                                min_dist = dist
                                best_pair = (idx1, idx2, c1, c2)
            
            if best_pair is None:
                break
            
            idx1, idx2, c1, c2 = best_pair
            
            # Find path from c1 to c2 within 'cells'
            # BFS on the grid restricted to 'cells'
            parent = {c1: None}
            queue = deque([c1])
            found = False
            while queue and not found:
                ci, cj = queue.popleft()
                if (ci, cj) == c2:
                    found = True
                    break
                for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ni, nj = ci+di, cj+dj
                    if (ni, nj) in cell_set and (ni, nj) not in parent:
                        parent[(ni, nj)] = (ci, cj)
                        queue.append((ni, nj))
            
            if found:
                # Add all cells on the path
                path_cell = c2
                while path_cell != c1:
                    included.add(path_cell)
                    path_cell = parent[path_cell]
                # Merge components
                new_comp = components[idx1] | components[idx2] | included
                remaining = [comp for idx, comp in enumerate(components) if idx != idx1 and idx != idx2]
                remaining.append(new_comp)
                components = remaining
            else:
                # Should not happen since original region is connected
                break
        
        return list(included)
    
    # Process each color
    for c in range(1, m + 1):
        cells = get_cells_of_color(c)
        if not cells:
            continue
        
        # Find which colors this color needs to be adjacent to
        required_adj_colors = set()
        for d in range(m + 1):
            if d != c and adj[c][d]:
                required_adj_colors.add(d)
        
        # Get minimal connected subset
        minimal_cells = find_minimal_connected(cells, required_adj_colors)
        
        # Place them in the result grid
        for (i, j) in minimal_cells:
            result_grid[i][j] = c
    
    # Output the result
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(map(str, result_grid[i])))
    print('\n'.join(out_lines))

solve()