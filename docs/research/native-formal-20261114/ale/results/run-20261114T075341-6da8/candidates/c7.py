import sys
from collections import deque

def solve():
    data = sys.stdin.read().split()
    idx = 0
    n = int(data[idx]); idx += 1
    m = int(data[idx]); idx += 1
    
    grid = []
    for i in range(n):
        row = [int(data[idx+j]) for j in range(n)]
        idx += n
        grid.append(row)
    
    # Build adjacency set: adj[c] = set of colors adjacent to c (including 0)
    adj = [set() for _ in range(m + 1)]
    
    # Boundary adjacencies with color 0
    for i in range(n):
        adj[grid[i][0]].add(0)
        adj[0].add(grid[i][0])
        adj[grid[i][n-1]].add(0)
        adj[0].add(grid[i][n-1])
    for j in range(n):
        adj[grid[0][j]].add(0)
        adj[0].add(grid[0][j])
        adj[grid[n-1][j]].add(0)
        adj[0].add(grid[n-1][j])
    
    # Internal adjacencies
    for i in range(n):
        for j in range(n):
            c1 = grid[i][j]
            if i + 1 < n:
                c2 = grid[i+1][j]
                if c1 != c2:
                    adj[c1].add(c2)
                    adj[c2].add(c1)
            if j + 1 < n:
                c2 = grid[i][j+1]
                if c1 != c2:
                    adj[c1].add(c2)
                    adj[c2].add(c1)
    
    # Count how many adjacent pairs exist between each pair of colors
    # pair_count[(c,d)] = number of edge-adjacent cell pairs between color c and d
    pair_count = {}
    for i in range(n):
        for j in range(n):
            c1 = grid[i][j]
            if i + 1 < n:
                c2 = grid[i+1][j]
                if c1 != c2:
                    key = (min(c1,c2), max(c1,c2))
                    pair_count[key] = pair_count.get(key, 0) + 1
            if j + 1 < n:
                c2 = grid[i][j+1]
                if c1 != c2:
                    key = (min(c1,c2), max(c1,c2))
                    pair_count[key] = pair_count.get(key, 0) + 1
    
    # Start with original grid
    out = [row[:] for row in grid]
    
    def get_cells(color):
        """Get all cells of a given color in current grid"""
        cells = []
        for i in range(n):
            for j in range(n):
                if out[i][j] == color:
                    cells.append((i,j))
        return cells
    
    def is_connected(cells):
        """Check if a set of cells is connected via edge adjacency"""
        if len(cells) <= 1:
            return True
        cell_set = set(cells)
        start = cells[0]
        visited = {start}
        dq = deque([start])
        while dq:
            ci, cj = dq.popleft()
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = ci+di, cj+dj
                if (ni,nj) in cell_set and (ni,nj) not in visited:
                    visited.add((ni,nj))
                    dq.append((ni,nj))
        return len(visited) == len(cell_set)
    
    def can_remove(i, j):
        """Check if cell (i,j) can be safely removed (set to 0)"""
        c = out[i][j]
        if c == 0:
            return False
        
        # Get neighbors' colors
        neighbor_colors = []
        for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
            ni, nj = i+di, j+dj
            if ni < 0 or ni >= n or nj < 0 or nj >= n:
                neighbor_colors.append(0)
            else:
                neighbor_colors.append(out[ni][nj])
        
        # Check connectivity after removal
        cells_c = get_cells(c)
        if (i,j) not in cells_c:
            return False
        remaining = [cell for cell in cells_c if cell != (i,j)]
        if not is_connected(remaining):
            return False
        
        # Check that all required adjacencies are preserved
        # For each neighbor color d != c, we need at least one other adjacent pair
        for d in neighbor_colors:
            if d == c:
                continue
            # Check if removing this cell eliminates the last adjacency between c and d
            key = (min(c,d), max(c,d))
            current_count = pair_count.get(key, 0)
            # This cell contributes to adjacency between c and d if d is a neighbor
            # We need to check if there's another cell of color c adjacent to a cell of color d
            # Simple check: count how many times this specific cell is involved in c-d adjacency
            # If it's the only one, we can't remove
            # Actually, let's just check: after removal, does any c-cell still touch a d-cell?
            # For efficiency, let's check if current_count > 1 OR if there's another touching pair
            if current_count <= 1:
                # This might be the only adjacency - verify by checking other cells
                # Find all cells of color c that are adjacent to color d
                found_other = False
                for ci, cj in remaining:
                    for di2, dj2 in [(-1,0),(1,0),(0,-1),(0,1)]:
                        ni2, nj2 = ci+di2, cj+dj2
                        if ni2 < 0 or ni2 >= n or nj2 < 0 or nj2 >= n:
                            nc = 0
                        else:
                            nc = out[ni2][nj2]
                        if nc == d:
                            found_other = True
                            break
                    if found_other:
                        break
                if not found_other:
                    return False
        
        return True
    
    # Greedy removal: repeatedly try to remove cells
    changed = True
    while changed:
        changed = False
        for i in range(n):
            for j in range(n):
                if out[i][j] != 0 and can_remove(i, j):
                    out[i][j] = 0
                    changed = True
    
    result_lines = [' '.join(map(str, row)) for row in out]
    print('\n'.join(result_lines))

solve()