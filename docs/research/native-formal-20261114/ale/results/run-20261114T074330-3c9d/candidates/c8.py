import sys
from collections import defaultdict, deque

def solve():
    data = sys.stdin.read().split()
    idx = 0
    n = int(data[idx]); idx += 1
    m = int(data[idx]); idx += 1
    
    grid = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(data[idx])); idx += 1
        grid.append(row)
    
    # Build adjacency graph between colors
    adj = [set() for _ in range(m+1)]
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            if i+1 < n and grid[i+1][j] != c:
                adj[c].add(grid[i+1][j])
                adj[grid[i+1][j]].add(c)
            if j+1 < n and grid[i][j+1] != c:
                adj[c].add(grid[i][j+1])
                adj[grid[i][j+1]].add(c)
    
    # Count cells per color
    counts = [0]*(m+1)
    for i in range(n):
        for j in range(n):
            counts[grid[i][j]] += 1
    
    # For each color, find a compact shape (minimize perimeter)
    # Use BFS to grow from seed cell
    def make_compact_shape(size, n):
        """Create a compact shape of given size on n x n grid.
        Returns list of (i,j) positions."""
        if size <= 0:
            return []
        # Try to fit in smallest possible bounding box
        # Start with 1x1, then expand
        best = None
        best_perim = float('inf')
        
        # Try different aspect ratios
        for w in range(1, min(n, int(size**0.5)+2)):
            h = (size + w - 1) // w
            if h > n or w > n:
                continue
            # Check if we can place this rectangle
            # Perimeter of the shape within the rectangle
            perim = 2*(w+h) if size == w*h else 2*(w+h)-2
            if perim < best_perim:
                best_perim = perim
                best = (w, h)
        
        if best is None:
            w, h = 1, size
        else:
            w, h = best
        
        # Generate positions in row-major order within w x h
        positions = []
        for r in range(h):
            for c in range(w):
                if len(positions) < size:
                    positions.append((r, c))
        
        return positions[:size]
    
    # Better approach: use actual grid placement with local search
    # First, assign initial positions using greedy method
    # Then optimize by moving shapes around
    
    # Initial assignment: place each color in a compact block
    # Sort colors by size descending for better packing
    colors_sorted = sorted(range(1, m+1), key=lambda c: -counts[c])
    
    # Create output grid
    out = [[0]*n for _ in range(n)]
    
    # Place colors one by one, finding good positions
    # Use a simple heuristic: try all positions, pick one that minimizes conflicts
    
    placed = {}
    for c in colors_sorted:
        size = counts[c]
        # Find compact shape
        positions = make_compact_shape(size, n)
        h = max(p[0] for p in positions)+1 if positions else 1
        w = max(p[1] for p in positions)+1 if positions else 1
        
        best_pos = None
        best_score = float('inf')
        
        for ri in range(n-h+1):
            for cj in range(n-w+1):
                # Check if position is valid (no overlap with already placed)
                valid = True
                conflict_count = 0
                for (dr, dc) in positions:
                    ni, nj = ri+dr, cj+dc
                    if out[ni][nj] != 0:
                        # Check if it's an adjacent color (allowed) or same color
                        if out[ni][nj] == c:
                            pass  # Same color, fine
                        elif out[ni][nj] in adj[c]:
                            conflict_count += 1  # Adjacent, OK but count
                        else:
                            valid = False
                            break
                if not valid:
                    continue
                
                # Also check boundary adjacency (color 0)
                boundary_adj = 0
                for (dr, dc) in positions:
                    ni, nj = ri+dr, cj+dc
                    # Check if this cell is on boundary of its region
                    for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                        mi, mj = ni+di, nj+dj
                        if mi < 0 or mi >= n or mj < 0 or mj >= n:
                            # Boundary - adjacent to color 0
                            if 0 in adj[c]:
                                boundary_adj += 1
                        elif out[mi][mj] == 0:
                            if 0 in adj[c]:
                                boundary_adj += 1
                
                score = conflict_count + boundary_adj*0.1
                if score < best_score:
                    best_score = score
                    best_pos = (ri, cj)
        
        if best_pos is None:
            # Fallback: just place anywhere available
            found = False
            for ri in range(n-h+1):
                for cj in range(n-w+1):
                    ok = True
                    for (dr, dc) in positions:
                        if out[ri+dr][cj+dc] != 0:
                            ok = False
                            break
                    if ok:
                        best_pos = (ri, cj)
                        found = True
                        break
                if found:
                    break
            if not found:
                # Very fallback: scatter
                pos_list = []
                for i in range(n):
                    for j in range(n):
                        if out[i][j] == 0:
                            pos_list.append((i,j))
                            if len(pos_list) >= size:
                                break
                    if len(pos_list) >= size:
                        break
                placed[c] = pos_list[:size]
                for (pi,pj) in pos_list[:size]:
                    out[pi][pj] = c
                continue
        
        ri, cj = best_pos
        for (dr, dc) in positions:
            out[ri+dr][cj+dc] = c
        placed[c] = [(ri+dr, cj+dc) for (dr,dc) in positions]
    
    # Verify and fix any issues
    # Check connectivity for each color
    for c in range(1, m+1):
        cells = placed.get(c, [])
        if not cells:
            continue
        cell_set = set(cells)
        start = cells[0]
        visited = {start}
        q = deque([start])
        while q:
            ci, cj = q.popleft()
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = ci+di, cj+dj
                if (ni,nj) in cell_set and (ni,nj) not in visited:
                    visited.add((ni,nj))
                    q.append((ni,nj))
        if len(visited) != len(cell_set):
            # Not connected - need to fix
            # Simple fix: re-place as compact shape
            size = len(cell_set)
            positions = make_compact_shape(size, n)
            h = max(p[0] for p in positions)+1 if positions else 1
            w = max(p[1] for p in positions)+1 if positions else 1
            # Clear old positions
            for (ci,cj) in cell_set:
                out[ci][cj] = 0
            # Find new position
            for ri in range(n-h+1):
                for cj in range(n-w+1):
                    ok = True
                    for (dr, dc) in positions:
                        if out[ri+dr][cj+dc] != 0:
                            ok = False
                            break
                    if ok:
                        for (dr, dc) in positions:
                            out[ri+dr][cj+dc] = c
                        placed[c] = [(ri+dr, cj+dc) for (dr,dc) in positions]
                        break
                else:
                    continue
                break
    
    # Output
    print('\n'.join(' '.join(map(str,row)) for row in out))

solve()
