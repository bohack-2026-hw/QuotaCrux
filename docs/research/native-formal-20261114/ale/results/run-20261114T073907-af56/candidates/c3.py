import sys
from collections import defaultdict, deque

def solve():
    data = sys.stdin.read().split()
    n = int(data[0])
    m = int(data[1])
    grid = []
    idx = 2
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(data[idx]))
            idx += 1
        grid.append(row)
    
    # Build adjacency graph between colors (including 0 for outside)
    adj = set()  # frozenset pairs of adjacent colors
    color_cells = defaultdict(list)
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            color_cells[c].append((i, j))
    
    # Find all adjacent color pairs
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            if i + 1 < n:
                d = grid[i+1][j]
                if c != d:
                    adj.add(frozenset([c, d]))
            if j + 1 < n:
                d = grid[i][j+1]
                if c != d:
                    adj.add(frozenset([c, d]))
    
    # Also check boundary cells against outside (color 0)
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                adj.add(frozenset([0, c]))
    
    # Now we need to place m colors on an n x n grid such that:
    # 1. Each color's cells are connected
    # 2. Adjacency relationships match exactly
    # 3. Maximize number of 0-colored cells
    
    # Strategy: Use a greedy approach with local search.
    # First, try to find a compact layout for the non-zero colors.
    
    # Key insight: We can think of this as graph embedding problem.
    # Each color is a node, edges represent required adjacencies.
    # We want to embed this graph on a grid where each node occupies connected cells.
    
    # Simple approach: Try to pack colors into small connected regions.
    # Start with each color as a single cell, then expand as needed.
    
    # For now, use a heuristic: arrange colors in a space-filling pattern.
    
    # Let's try a different approach: use the original map but remove some cells
    # while maintaining connectivity and adjacency.
    
    # Actually, let's try a constructive approach:
    # 1. Identify which colors are on the boundary (adjacent to 0)
    # 2. Place boundary colors around the perimeter
    # 3. Fill interior with remaining colors
    
    # Colors adjacent to 0 must be placed on the boundary of our map.
    boundary_colors = set()
    for pair in adj:
        if 0 in pair:
            other = list(pair)[0] if 0 in pair else list(pair)[1]
            if other != 0:
                boundary_colors.add(other)
    
    # Non-boundary colors
    all_colors = set(range(1, m+1))
    interior_colors = all_colors - boundary_colors
    
    # Create output grid initialized to 0
    out = [[0]*n for _ in range(n)]
    
    # Place boundary colors along the perimeter
    # Top row: left to right
    # Right col: top to bottom
    # Bottom row: right to left
    # Left col: bottom to top
    
    perimeter_positions = []
    for j in range(n):
        perimeter_positions.append((0, j))
    for i in range(1, n):
        perimeter_positions.append((i, n-1))
    for j in range(n-2, -1, -1):
        perimeter_positions.append((n-1, j))
    for i in range(n-2, 0, -1):
        perimeter_positions.append((i, 0))
    
    # Assign boundary colors to perimeter positions
    bc_list = list(boundary_colors)
    bc_list.sort()
    
    # We need to ensure that boundary colors that are adjacent to each other
    # are placed next to each other on the perimeter.
    # This is a complex constraint satisfaction problem.
    
    # For simplicity, let's just assign them in order and hope it works,
    # then fix issues with local search.
    
    pos_idx = 0
    for c in bc_list:
        if pos_idx >= len(perimeter_positions):
            break
        i, j = perimeter_positions[pos_idx]
        out[i][j] = c
        pos_idx += 1
    
    # Place interior colors in the center area
    ic_list = list(interior_colors)
    ic_list.sort()
    
    # Center region: rows 1..n-2, cols 1..n-2
    center_positions = []
    for i in range(1, n-1):
        for j in range(1, n-1):
            center_positions.append((i, j))
    
    pos_idx = 0
    for c in ic_list:
        if pos_idx >= len(center_positions):
            break
        i, j = center_positions[pos_idx]
        out[i][j] = c
        pos_idx += 1
    
    # Now we have a basic placement. But we need to verify:
    # 1. Connectivity of each color
    # 2. Correct adjacency relationships
    
    # Since each color currently has only 1 cell, connectivity is trivially satisfied.
    # But adjacency might not be correct.
    
    # Check current adjacencies
    current_adj = set()
    for i in range(n):
        for j in range(n):
            c = out[i][j]
            if i + 1 < n:
                d = out[i+1][j]
                if c != d and c != 0 and d != 0:
                    current_adj.add(frozenset([c, d]))
                elif c == 0 and d != 0:
                    current_adj.add(frozenset([0, d]))
                elif c != 0 and d == 0:
                    current_adj.add(frozenset([0, c]))
            if j + 1 < n:
                d = out[i][j+1]
                if c != d and c != 0 and d != 0:
                    current_adj.add(frozenset([c, d]))
                elif c == 0 and d != 0:
                    current_adj.add(frozenset([0, d]))
                elif c != 0 and d == 0:
                    current_adj.add(frozenset([0, c]))
    
    # Boundary adjacencies with 0
    for i in range(n):
        for j in range(n):
            c = out[i][j]
            if c != 0 and (i == 0 or i == n-1 or j == 0 or j == n-1):
                current_adj.add(frozenset([0, c]))
    
    # Compare with required adjacencies
    missing = adj - current_adj
    extra = current_adj - adj
    
    # If there are missing adjacencies, we need to add cells to connect those colors.
    # If there are extra adjacencies, we need to separate those colors.
    
    # This is getting complex. Let's try a simpler approach first:
    # Just output the original grid. It's always valid.
    # Score will be E+1 where E is the number of 0s in original grid.
    # Since original grid has no 0s (all cells are colored 1..m), score = 1 per case.
    
    # Wait, the input says 1<=c_{i,j}<=m, so there are NO 0s in the input!
    # That means the original map uses ALL cells, and score would be 1.
    
    # To get a better score, we MUST create 0s by removing some cells.
    
    # Let me reconsider the approach. We need to find a subset of cells for each color
    # such that:
    # - Each color's selected cells are connected
    # - The adjacency graph matches
    # - Total selected cells is minimized (maximizing 0s)
    
    # This is essentially a minimum connected subgraph problem for each color,
    # subject to global adjacency constraints.
    
    # Heuristic approach:
    # 1. For each color, find its bounding box in the original map
    # 2. Try to shrink each color to a minimal connected region
    # 3. Ensure adjacencies are preserved
    
    # Let's try: for each color, keep only one cell (the "representative"),
    # but this won't work because we need adjacencies.
    
    # Better: identify critical adjacencies and ensure those pairs have
    # at least one adjacent pair of cells.
    
    # Algorithm:
    # 1. For each color, pick a representative cell
    # 2. For each required adjacency (c,d), ensure rep(c) and rep(d) are adjacent
    #    or can be made adjacent by adding intermediate cells
    # 3. Minimize total cells used
    
    # This is still complex. Let's try a practical heuristic:
    # Use BFS from each color's cells, keeping only the necessary ones.
    
    # Actually, let's try a much simpler approach that might work well:
    # Arrange all colors in a compact block, like a spiral or snake pattern.
    
    # The key constraint is that the adjacency graph must be preserved.
    # If we can find a planar embedding of the adjacency graph on the grid,
    # we're good.
    
    # For now, let's implement a reasonable heuristic:
    # 1. Sort colors by their position in the original map (top-left to bottom-right)
    # 2. Place them in a similar order in the new map
    # 3. Use connected regions of appropriate size
    
    # Let's compute the centroid of each color in the original map
    centroids = {}
    for c in range(1, m+1):
        cells = color_cells[c]
        avg_i = sum(i for i,j in cells) / len(cells)
        avg_j = sum(j for i,j in cells) / len(cells)
        centroids[c] = (avg_i, avg_j)
    
    # Sort colors by centroid position
    sorted_colors = sorted(range(1, m+1), key=lambda c: (centroids[c][0], centroids[c][1]))
    
    # Now place them in the new map in a space-filling curve order
    # that preserves relative positions
    
    # Create a Hilbert-like curve or simple row-major ordering
    # and assign colors to maintain adjacency relationships
    
    # For simplicity, let's use a different strategy:
    # Keep the overall shape but remove redundant cells.
    
    # For each color, do a BFS and keep only the shortest paths between
    # critical junction points.
    
    # This is getting too complex for now. Let me implement a working solution
    # that produces valid output with some optimization.
    
    # Practical approach: 
    # 1. Start with the original grid
    # 2. For each color, try to remove cells that are "leaves" in the 
    #    spanning tree of that color's cells, as long as it doesn't break
    #    any required adjacency
    
    # Step 1: Build spanning tree for each color
    # Step 2: Identify leaf nodes (degree 1 in spanning tree)
    # Step 3: Remove leaves if they don't participate in any required adjacency
    #         with another color
    
    # A cell of color c participates in an adjacency with color d if it's
    # adjacent to a cell of color d in the original map.
    
    # Let's mark which cells are "essential" for adjacencies
    essential = [[False]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check if this cell is adjacent to a different color
            for di, dj in [(0,1),(0,-1),(1,0),(-1,0)]:
                ni, nj = i+di, j+dj
                if 0 <= ni < n and 0 <= nj < n:
                    d = grid[ni][nj]
                    if d != c:
                        essential[i][j] = True
                        break
                else:
                    # Boundary - adjacent to outside (0)
                    essential[i][j] = True
                    break
    
    # Now, for each color, build a spanning tree and try to prune non-essential leaves
    result = [row[:] for row in grid]
    
    for c in range(1, m+1):
        cells = color_cells[c]
        if not cells:
            continue
        
        # Build adjacency within this color
        cell_set = set(cells)
        adj_within = defaultdict(set)
        for i, j in cells:
            for di, dj in [(0,1),(0,-1),(1,0),(-1,0)]:
                ni, nj = i+di, j+dj
                if (ni, nj) in cell_set:
                    adj_within[(i,j)].add((ni,nj))
        
        # BFS to build spanning tree
        start = cells[0]
        visited = {start}
        parent = {start: None}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            for nb in adj_within[cur]:
                if nb not in visited:
                    visited.add(nb)
                    parent[nb] = cur
                    queue.append(nb)
        
        # Get leaves (degree 1 in spanning tree, excluding root)
        degree_in_tree = defaultdict(int)
        for node in visited:
            if parent[node] is not None:
                degree_in_tree[node] += 1
                degree_in_tree[parent[node]] += 1
        
        leaves = [node for node in visited if degree_in_tree[node] == 1 and node != start]
        
        # Try to remove non-essential leaves
        removed = set()
        for leaf in leaves:
            if not essential[leaf[0]][leaf[1]]:
                # Check if removing this leaf breaks any adjacency requirement
                # The leaf is only connected to its parent in the tree
                # If the leaf is not essential, we can remove it
                removed.add(leaf)
        
        # Apply removals
        for i, j in removed:
            result[i][j] = 0
    
    # Verify the result
    # Check connectivity for each color
    for c in range(1, m+1):
        cells = [(i,j) for i in range(n) for j in range(n) if result[i][j] == c]
        if not cells:
            # Color disappeared! This is invalid.
            # Restore this color
            for i, j in color_cells[c]:
                result[i][j] = c
            continue
        
        # BFS to check connectivity
        start = cells[0]
        visited = {start}
        queue = deque([start])
        cell_set = set(cells)
        while queue:
            cur = queue.popleft()
            for di, dj in [(0,1),(0,-1),(1,0),(-1,0)]:
                ni, nj = cur[0]+di, cur[1]+dj
                if (ni,nj) in cell_set and (ni,nj) not in visited:
                    visited.add((ni,nj))
                    queue.append((ni,nj))
        
        if len(visited) != len(cells):
            # Not connected, restore
            for i, j in color_cells[c]:
                result[i][j] = c
    
    # Check adjacencies
    final_adj = set()
    for i in range(n):
        for j in range(n):
            c = result[i][j]
            if i + 1 < n:
                d = result[i+1][j]
                if c != d:
                    final_adj.add(frozenset([c, d]))
            if j + 1 < n:
                d = result[i][j+1]
                if c != d:
                    final_adj.add(frozenset([c, d]))
    
    # Boundary adjacencies
    for i in range(n):
        for j in range(n):
            c = result[i][j]
            if c != 0 and (i == 0 or i == n-1 or j == 0 or j == n-1):
                final_adj.add(frozenset([0, c]))
    
    # Verify adjacencies match
    if final_adj != adj:
        # Invalid, restore original
        result = [row[:] for row in grid]
    
    # Count zeros
    zero_count = sum(1 for i in range(n) for j in range(n) if result[i][j] == 0)
    
    # Output
    print('\n'.join(' '.join(str(x) for x in row) for row in result))

solve()
