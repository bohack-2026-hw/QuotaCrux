import sys
from collections import deque

def solve():
    lines = sys.stdin.read().splitlines()
    n, m = map(int, lines[0].split())
    grid = []
    for i in range(n):
        row = list(map(int, lines[i+1].split()))
        grid.append(row)
    
    result_grid = [[0] * n for _ in range(n)]
    
    # For each color, find minimal connected subset that preserves adjacencies
    for c in range(1, m + 1):
        # Find all cells of this color
        cells_of_color = set()
        for i in range(n):
            for j in range(n):
                if grid[i][j] == c:
                    cells_of_color.add((i, j))
        
        if not cells_of_color:
            continue
        
        # Find boundary cells: cells that have at least one neighbor of a different color (or outside)
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
                    # Outside the grid means adjacent to color 0
                    is_boundary = True
                    break
            if is_boundary:
                boundary_cells.add((i, j))
        
        # If no boundary cells (shouldn't happen), keep all
        if not boundary_cells:
            for (i, j) in cells_of_color:
                result_grid[i][j] = c
            continue
        
        # Check if boundary cells are connected
        # BFS from one boundary cell within boundary_cells
        start_cell = next(iter(boundary_cells))
        visited = {start_cell}
        queue = deque([start_cell])
        while queue:
            ci, cj = queue.popleft()
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = ci+di, cj+dj
                if (ni, nj) in boundary_cells and (ni, nj) not in visited:
                    visited.add((ni, nj))
                    queue.append((ni, nj))
        
        if len(visited) == len(boundary_cells):
            # Boundary cells are connected, use them directly
            kept_cells = boundary_cells
        else:
            # Boundary cells are not connected, need to add internal cells to connect them
            # Use greedy approach: repeatedly connect closest pair of components
            components = []
            unvisited = set(boundary_cells)
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
                        if (ni, nj) in cells_of_color and (ni, nj) not in parent:
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