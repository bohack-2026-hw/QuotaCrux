import sys
from collections import deque

def solve():
    lines = sys.stdin.read().splitlines()
    n, m = map(int, lines[0].split())
    grid = []
    for i in range(n):
        row = list(map(int, lines[i+1].split()))
        grid.append(row)
    
    # For each color, find a spanning tree of its cells and keep only the tree cells
    result_grid = [[0] * n for _ in range(n)]
    
    for c in range(1, m + 1):
        # Find all cells of this color
        cells_of_color = set()
        for i in range(n):
            for j in range(n):
                if grid[i][j] == c:
                    cells_of_color.add((i, j))
        
        if not cells_of_color:
            continue
        
        if len(cells_of_color) == 1:
            (i, j) = next(iter(cells_of_color))
            result_grid[i][j] = c
            continue
        
        # Find a BFS spanning tree from an arbitrary cell
        start_cell = next(iter(cells_of_color))
        parent = {start_cell: None}
        queue = deque([start_cell])
        
        while queue:
            ci, cj = queue.popleft()
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = ci+di, cj+dj
                if (ni, nj) in cells_of_color and (ni, nj) not in parent:
                    parent[(ni, nj)] = (ci, cj)
                    queue.append((ni, nj))
        
        # All cells should be visited since the region is connected
        # Keep all cells that are part of the spanning tree (which is all cells)
        # Actually, we need to keep only the cells on the tree edges
        # But every cell except the root has exactly one parent, so they're all on the tree
        # This means we'd keep all cells again...
        
        # Let me think differently: we want to minimize the number of cells.
        # The minimum connected set containing all boundary cells is what we need.
        # But as we saw, boundary cells might not be connected.
        
        # New approach: for each color, keep only the cells that are "necessary"
        # A cell is necessary if removing it would either:
        # 1. Disconnect the region, OR
        # 2. Remove an adjacency with another color
        
        # Simpler: just keep all cells that have at least one neighbor of a different color
        # (boundary cells), plus any interior cells needed to connect them.
        
        # Let's try: keep all boundary cells, then add interior cells to make them connected
        boundary_cells = set()
        for (i, j) in cells_of_color:
            is_boundary = False
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = i+di, j+dj
                if 0 <= ni < n and 0 <= nj < n:
                    if grid[ni][nj] != c:
                        is_boundary = True
                        break
                else:
                    is_boundary = True
                    break
            if is_boundary:
                boundary_cells.add((i, j))
        
        # Check if boundary cells are connected
        if not boundary_cells:
            # Shouldn't happen, but keep all cells
            for (i, j) in cells_of_color:
                result_grid[i][j] = c
            continue
        
        # BFS from one boundary cell within boundary_cells
        start_b = next(iter(boundary_cells))
        visited_b = {start_b}
        queue_b = deque([start_b])
        while queue_b:
            ci, cj = queue_b.popleft()
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = ci+di, cj+dj
                if (ni, nj) in boundary_cells and (ni, nj) not in visited_b:
                    visited_b.add((ni, nj))
                    queue_b.append((ni, nj))
        
        if len(visited_b) == len(boundary_cells):
            # Boundary cells are connected, use them
            kept_cells = boundary_cells
        else:
            # Need to add interior cells to connect boundary components
            # Find connected components of boundary_cells
            components = []
            unvisited = set(boundary_cells)
            while unvisited:
                comp = set()
                start = next(iter(unvisited))
                q = deque([start])
                comp.add(start)
                unvisited.remove(start)
                while q:
                    ci, cj = q.popleft()
                    for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                        ni, nj = ci+di, cj+dj
                        if (ni, nj) in unvisited:
                            unvisited.remove((ni, nj))
                            comp.add((ni, nj))
                            q.append((ni, nj))
                components.append(comp)
            
            # Greedily connect components by adding shortest paths through cells_of_color
            included = set(boundary_cells)
            while len(components) > 1:
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
                
                # Find path from c1 to c2 within cells_of_color using BFS
                par = {c1: None}
                q = deque([c1])
                found = False
                while q and not found:
                    ci, cj = q.popleft()
                    if (ci, cj) == c2:
                        found = True
                        break
                    for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                        ni, nj = ci+di, cj+dj
                        if (ni, nj) in cells_of_color and (ni, nj) not in par:
                            par[(ni, nj)] = (ci, cj)
                            q.append((ni, nj))
                
                if found:
                    path_cell = c2
                    while path_cell != c1:
                        included.add(path_cell)
                        path_cell = par[path_cell]
                    new_comp = components[idx1] | components[idx2] | included
                    remaining = [comp for idx, comp in enumerate(components) if idx != idx1 and idx != idx2]
                    remaining.append(new_comp)
                    components = remaining
                else:
                    break
            
            kept_cells = included
        
        # Place kept cells in result_grid
        for (i, j) in kept_cells:
            result_grid[i][j] = c
    
    # Output the result
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(map(str, result_grid[i])))
    print('\n'.join(out_lines))

solve()