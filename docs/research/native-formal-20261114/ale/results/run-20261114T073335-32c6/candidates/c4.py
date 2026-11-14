import sys
from collections import deque

def solve():
    lines = sys.stdin.read().splitlines()
    n, m = map(int, lines[0].split())
    grid = []
    for i in range(n):
        row = list(map(int, lines[i+1].split()))
        grid.append(row)
    
    # Step 1: For each color, find all boundary cells (cells adjacent to a different color or outside)
    # Then keep only the connected component containing these boundary cells
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
        
        # If no boundary cells (shouldn't happen since region is connected and non-empty), keep all
        if not boundary_cells:
            for (i, j) in cells_of_color:
                result_grid[i][j] = c
            continue
        
        # BFS from boundary cells within cells_of_color to find the connected component
        # Since the original region is connected, all boundary cells are in the same component
        visited = set()
        queue = deque()
        for cell in boundary_cells:
            if cell not in visited:
                visited.add(cell)
                queue.append(cell)
        
        while queue:
            ci, cj = queue.popleft()
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = ci+di, cj+dj
                if (ni, nj) in cells_of_color and (ni, nj) not in visited:
                    visited.add((ni, nj))
                    queue.append((ni, nj))
        
        # Place the visited cells in result_grid
        for (i, j) in visited:
            result_grid[i][j] = c
    
    # Output the result
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(map(str, result_grid[i])))
    print('\n'.join(out_lines))

solve()