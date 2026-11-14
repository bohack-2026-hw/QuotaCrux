import sys
from collections import deque

def solve():
    lines = sys.stdin.read().splitlines()
    n, m = map(int, lines[0].split())
    grid = []
    for i in range(n):
        row = list(map(int, lines[i+1].split()))
        grid.append(row)
    
    # For each color, find cells that can be safely removed:
    # A cell can be removed if:
    # 1. All its neighbors are the same color (it's an interior cell)
    # 2. Removing it doesn't disconnect the region (it's not an articulation point)
    
    result_grid = [row[:] for row in grid]
    
    for c in range(1, m + 1):
        # Find all cells of this color
        cells_of_color = set()
        for i in range(n):
            for j in range(n):
                if grid[i][j] == c:
                    cells_of_color.add((i, j))
        
        if len(cells_of_color) <= 1:
            continue
        
        # Find interior cells: cells where all 4 neighbors are also color c
        interior_cells = []
        for (i, j) in cells_of_color:
            is_interior = True
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = i+di, j+dj
                if 0 <= ni < n and 0 <= nj < n:
                    if grid[ni][nj] != c:
                        is_interior = False
                        break
                else:
                    # Outside the grid means adjacent to color 0, so not interior
                    is_interior = False
                    break
            if is_interior:
                interior_cells.append((i, j))
        
        # Try to remove interior cells one by one, checking connectivity
        # We'll use a greedy approach: try removing each interior cell,
        # check if the remaining cells are still connected
        
        def is_connected(cell_set):
            """Check if a set of cells is connected."""
            if not cell_set:
                return True
            start = next(iter(cell_set))
            visited = {start}
            queue = deque([start])
            while queue:
                ci, cj = queue.popleft()
                for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ni, nj = ci+di, cj+dj
                    if (ni, nj) in cell_set and (ni, nj) not in visited:
                        visited.add((ni, nj))
                        queue.append((ni, nj))
            return len(visited) == len(cell_set)
        
        current_cells = set(cells_of_color)
        
        # Sort interior cells by some heuristic (e.g., distance from boundary)
        # For simplicity, just try them in order
        for cell in interior_cells:
            test_cells = current_cells - {cell}
            if is_connected(test_cells):
                # Safe to remove
                current_cells = test_cells
                result_grid[cell[0]][cell[1]] = 0
        
    # Output the result
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(map(str, result_grid[i])))
    print('\n'.join(out_lines))

solve()