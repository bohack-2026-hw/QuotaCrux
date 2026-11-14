import sys
from collections import deque

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
    
    # Build adjacency graph between colors (including 0)
    adj = [[False] * (m + 1) for _ in range(m + 1)]
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check right and down neighbors to avoid double counting
            if i + 1 < n:
                d = grid[i+1][j]
                if c != d:
                    adj[c][d] = True
                    adj[d][c] = True
            if j + 1 < n:
                d = grid[i][j+1]
                if c != d:
                    adj[c][d] = True
                    adj[d][c] = True
            # Boundary: adjacent to 0
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                if c != 0:
                    adj[c][0] = True
                    adj[0][c] = True
    
    # For each color, find which other colors it's adjacent to
    # We need to place tiles such that:
    # 1. Each color's tiles are connected
    # 2. Adjacency relationships match exactly
    # 3. Maximize number of 0 tiles
    
    # Strategy: Place each color as a single tile if possible.
    # A color c can be placed at position (i,j) if:
    # - It's not already occupied
    # - For every color d adjacent to c, there's a tile of d adjacent to (i,j)
    # - For every color d NOT adjacent to c, no tile of d is adjacent to (i,j)
    #   (except 0 which is always "available" outside)
    
    # Actually, let me think more carefully. If we place one tile per color,
    # then color c at (i,j) is adjacent to colors at (i-1,j), (i+1,j), (i,j-1), (i,j+1).
    # The set of adjacent colors must match exactly the adjacency list of c.
    # Also, boundary positions are adjacent to 0.
    
    # Let's try: assign each color to a cell. Use backtracking/greedy.
    # Since m=100 and n=50, we have 2500 cells but only need 100.
    
    # Better approach: Think of it as placing 100 colored tiles on a 50x50 grid
    # such that the induced adjacency graph matches the original.
    
    # Key insight: If color c is adjacent to color d in the original map,
    # they must be edge-adjacent in the new map. If not adjacent, they must not be.
    
    # Let's use a greedy placement strategy:
    # 1. Sort colors by degree (number of adjacent colors) descending
    # 2. Place high-degree colors first, trying to satisfy constraints
    
    # Actually, let me think about this differently. The problem is equivalent to:
    # Find an embedding of the adjacency graph into the grid graph where
    # each vertex maps to a connected set of cells, and edges correspond to
    # cell adjacencies.
    
    # Simplest valid solution: keep the original map (score = count of 0s + 1)
    # But we can do better by compacting.
    
    # Let me try a different approach: place each color as exactly 1 cell.
    # This requires that the adjacency graph can be embedded in the grid graph
    # with each vertex mapped to one cell, preserving all adjacencies.
    
    # The grid graph has max degree 4 (interior) or less (boundary/corner).
    # So any color with degree > 4 cannot be a single interior cell.
    # Colors with degree > 4 need multiple cells.
    
    # Let me compute degrees:
    deg = [0] * (m + 1)
    for c in range(1, m + 1):
        for d in range(m + 1):
            if c != d and adj[c][d]:
                deg[c] += 1
    
    # For colors with degree <= 4, try to place as single cell.
    # For colors with degree > 4, they need multiple cells.
    
    # Let me try a simpler approach first: just output the original map.
    # Then improve from there.
    
    # Actually, let me try to create a compact map using a specific layout.
    # 
    # Idea: Arrange colors in a pattern where adjacent colors in the graph
    # are placed next to each other. 
    
    # Let me try: place colors in a spiral or snake pattern, ensuring
    # that graph-adjacent colors are grid-adjacent.
    
    # This is essentially a graph embedding problem which is NP-hard in general.
    # But for scoring purposes, even a partial improvement helps.
    
    # Let me try a practical approach:
    # 1. Start with original map
    # 2. Try to shrink each color region by removing redundant cells
    # 3. Ensure connectivity and adjacency are preserved
    
    # Simpler: Let me just try to place each color in one cell where possible.
    # Use a constraint satisfaction approach.
    
    # For now, let me implement a basic version that tries to minimize tiles.
    
    # Approach: Greedy placement
    # - Create empty grid filled with 0
    # - Place colors one by one, choosing positions that satisfy constraints
    
    result = [[0]*n for _ in range(n)]
    placed = [False] * (m + 1)
    
    # Order colors by degree descending (harder ones first)
    order = list(range(1, m+1))
    order.sort(key=lambda c: -deg[c])
    
    def get_adj_colors(c):
        return [d for d in range(m+1) if d != c and adj[c][d]]
    
    def check_placement(grid, pos, color, m_val, n_val):
        """Check if placing color at pos is consistent with already-placed colors."""
        i, j = pos
        # Get neighbors in grid
        neighbors = []
        for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
            ni, nj = i+di, j+dj
            if 0 <= ni < n_val and 0 <= nj < n_val:
                neighbors.append((ni, nj))
            else:
                neighbors.append(None)  # boundary -> adjacent to 0
        
        for nb in neighbors:
            if nb is None:
                # Adjacent to 0 (outside)
                if color != 0 and not adj[color][0]:
                    return False
                continue
            ni, nj = nb
            nc = grid[ni][nj]
            if nc == 0:
                # Adjacent to 0 in grid - this is fine, 0 is everywhere
                continue
            if nc == color:
                continue  # same color, no issue
            # Different color nc
            if adj[color][nc]:
                # They should be adjacent - OK
                pass
            else:
                # They should NOT be adjacent - violation
                return False
        return True
    
    def would_violate(grid, pos, color, m_val, n_val):
        """Check if placing color at pos causes non-adjacent colors to become adjacent."""
        i, j = pos
        for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
            ni, nj = i+di, j+dj
            if 0 <= ni < n_val and 0 <= nj < n_val:
                nc = grid[ni][nj]
                if nc != 0 and nc != color and not adj[color][nc]:
                    return True
        return False
    
    # Try to place each color as a single cell
    success_count = 0
    for color in order:
        placed_here = False
        required_neighbors = set(get_adj_colors(color))
        
        best_pos = None
        best_score = -1
        
        for i in range(n):
            for j in range(n):
                if result[i][j] != 0:
                    continue
                # Check if this position works
                ok = True
                satisfied = set()
                for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ni, nj = i+di, j+dj
                    if 0 <= ni < n and 0 <= nj < n:
                        nc = result[ni][nj]
                        if nc != 0 and nc != color:
                            if not adj[color][nc]:
                                ok = False
                                break
                            satisfied.add(nc)
                    else:
                        # Boundary - adjacent to 0
                        if color != 0 and not adj[color][0]:
                            ok = False
                            break
                        satisfied.add(0)
                
                if not ok:
                    continue
                
                # Score: prefer positions that satisfy more required adjacencies
                score = len(satisfied & required_neighbors)
                # Penalize if we're creating unwanted adjacencies (shouldn't happen due to ok check)
                if score > best_score:
                    best_score = score
                    best_pos = (i, j)
        
        if best_pos is not None:
            result[best_pos[0]][best_pos[1]] = color
            placed[color] = True
            success_count += 1
    
    # For unplaced colors, we need to add more cells.
    # This gets complex. For now, let's verify what we have and fill remaining.
    
    # Actually, this single-cell approach won't work well because most colors
    # have multiple neighbors that can't all fit around one cell.
    
    # Let me take a completely different approach: use the original map but
    # try to compress it.
    
    # New strategy: Just output original map as baseline, then try improvements.
    # The original map is always valid.
    
    # Let me count 0s in original:
    zero_count = sum(1 for i in range(n) for j in range(n) if grid[i][j] == 0)
    
    # Print original map
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(str(grid[i][j]) for j in range(n)))
    print('\n'.join(out_lines))

solve()
