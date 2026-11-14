import sys
from collections import deque

def solve():
    data = sys.stdin.read().split()
    if not data:
        return
    idx = 0
    n = int(data[idx]); idx += 1
    m = int(data[idx]); idx += 1
    grid = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(data[idx])); idx += 1
        grid.append(row)
    
    # Build adjacency graph between colors (including 0 for outside)
    adj = [[False] * (m + 1) for _ in range(m + 1)]
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check right and down neighbors to avoid duplicates
            if i + 1 < n:
                d = grid[i+1][j]
                adj[c][d] = True
                adj[d][c] = True
            if j + 1 < n:
                d = grid[i][j+1]
                adj[c][d] = True
                adj[d][c] = True
            # Boundary: adjacent to outside (color 0)
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                adj[c][0] = True
                adj[0][c] = True
    
    # For each color, find its cells
    cells_of_color = [[] for _ in range(m + 1)]
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            cells_of_color[c].append((i, j))
    
    # Strategy: We want to minimize the number of non-zero cells.
    # Each color must be connected. Adjacency constraints must be preserved.
    # 
    # Key insight: The problem is equivalent to finding a planar embedding-like structure.
    # But since we're on a grid, let's use a simpler approach:
    # 
    # Approach: Place each color as a small connected blob. Try to pack them tightly.
    # 
    # A practical heuristic:
    # 1. Start with each color occupying just 1 cell (if possible).
    # 2. Colors that are adjacent must have their blobs touching.
    # 3. Use local search / simulated annealing to optimize placement.
    # 
    # Given time constraints, let's try a constructive approach:
    # - Sort colors by degree (number of adjacent colors) descending.
    # - Place high-degree colors first near center.
    # - Ensure connectivity and adjacency.
    # 
    # Actually, let's think differently. The minimum number of cells per color is 1.
    # Total minimum non-zero cells = m = 100. So max E = 2500 - 100 = 2400.
    # Score = E + 1 = 2401 per test case ideally.
    # 
    # But can we achieve 1 cell per color? Only if the adjacency graph can be embedded
    # such that each node occupies exactly 1 grid cell and adjacent nodes' cells touch.
    # This requires the adjacency graph to be a subgraph of the grid graph (plus boundary edges to 0).
    # 
    # Since the original map has connected regions, the adjacency graph is planar.
    # A single-cell-per-color solution works if we can place all 100 colors on distinct grid
    # cells such that two colors are adjacent iff their cells share an edge (or one is on boundary
    # for color 0 adjacency).
    # 
    # Let's try: assign each color a unique position on the 50x50 grid.
    # We need to satisfy: for each pair (c,d), c~d in adj graph iff positions are adjacent.
    # Also, boundary cells are adjacent to 0.
    # 
    # This is essentially a graph embedding problem. Let's use a greedy + local search approach.
    # 
    # Simpler feasible approach: Use the original grid but shrink each color region to its
    # minimum bounding box or a smaller connected subset while preserving adjacencies.
    # 
    # Let's try: for each color, keep only a minimal connected subset that preserves all
    # adjacencies. Then compact the whole thing.
    # 
    # Practical approach given complexity: 
    # 1. For each color, select a representative cell.
    # 2. Try to place representatives on a grid maintaining adjacency.
    # 3. If conflicts, expand some colors to multiple cells.
    # 
    # Given the 2-second time limit and Python, let's implement a reasonable heuristic:
    # 
    # Heuristic: Place colors in a spiral or grid pattern, ensuring adjacencies.
    # 
    # Let me implement a simpler but effective approach:
    # - Create a new 50x50 grid initialized to 0.
    # - Assign each color a home position using a space-filling curve.
    # - Adjust to maintain adjacency constraints.
    # 
    # Actually, the most reliable approach within time limits:
    # Keep the original structure but remove redundant cells from each color region,
    # keeping only those needed for connectivity and adjacency.
    
    # Step 1: For each color, determine which cells are "essential" for adjacency.
    # A cell of color c is essential if it's adjacent to a different color (or boundary for 0-adjacency).
    # 
    # Step 2: Find a minimum connected subgraph spanning all essential cells for each color.
    # 
    # Step 3: Place these subsets back into a compact arrangement.
    
    # Due to complexity, let's do a simpler version:
    # For each color, keep a path connecting all its boundary-adjacent cells.
    
    # Even simpler: just output a valid solution where each color gets a small block.
    # Let's assign positions systematically.
    
    # Generate positions for each color to maximize zero cells.
    # We'll use a greedy placement with conflict resolution.
    
    pos = {}  # color -> list of (i,j) positions
    used = set()
    
    # Order colors: those with more adjacencies first
    degrees = [sum(1 for d in range(m+1) if adj[c][d]) for c in range(m+1)]
    order = sorted(range(1, m+1), key=lambda c: -degrees[c])
    
    # Try to place each color at a single cell first
    # Grid positions available
    all_positions = [(i, j) for i in range(n) for j in range(n)]
    
    # For single-cell placement, check if adjacency constraints can be met.
    # Two colors c,d are adjacent iff their single cells are grid-adjacent.
    # Also, a color on boundary is adjacent to 0.
    # 
    # This is a constraint satisfaction problem. Let's try random assignment + repair.
    # 
    # Given time, let's use a simple deterministic layout:
    # Arrange colors in rows, 10 per row (since 100 colors, 10 rows x 10 cols).
    # But this may not preserve adjacencies correctly.
    # 
    # Safest approach that guarantees correctness: use the original grid.
    # But score would be low. Let's try to improve by removing interior cells.
    
    # For each color, identify cells that are NOT on the boundary of the color region
    # (i.e., all 4 neighbors are same color). These can potentially be removed.
    # But removing them might break connectivity.
    
    # Let's compute for each color which cells can be safely removed while maintaining:
    # 1. Connectivity of the remaining cells
    # 2. All adjacency relations with other colors
    
    result_grid = [row[:] for row in grid]
    
    for c in range(1, m+1):
        cells = cells_of_color[c]
        if len(cells) <= 1:
            continue
        
        cell_set = set(cells)
        
        # Essential cells: those adjacent to a different color or boundary
        essential = set()
        for (i, j) in cells:
            is_essential = False
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = i+di, j+dj
                if ni < 0 or ni >= n or nj < 0 or nj >= n:
                    is_essential = True
                    break
                if grid[ni][nj] != c:
                    is_essential = True
                    break
            if is_essential:
                essential.add((i, j))
        
        if len(essential) <= 1:
            continue
        
        # Find a tree connecting all essential cells using only cells of color c.
        # Use BFS from one essential cell, adding edges to build a spanning tree.
        start = next(iter(essential))
        parent = {start: None}
        queue = deque([start])
        visited = {start}
        
        while queue:
            cur = queue.popleft()
            ci, cj = cur
            for di, dj in [(-1,0),(1,0),(0,-1),(0,1)]:
                ni, nj = ci+di, cj+dj
                if (ni, nj) in cell_set and (ni, nj) not in visited:
                    visited.add((ni, nj))
                    parent[(ni, nj)] = cur
                    queue.append((ni, nj))
                    if len(visited & essential) == len(essential):
                        break
            if len(visited & essential) == len(essential):
                break
        
        # The visited set contains a connected subgraph including all essential cells.
        # Mark non-essential cells not in this subgraph as removable.
        for (i, j) in cells:
            if (i, j) not in visited:
                result_grid[i][j] = 0
    
    # Output
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(str(result_grid[i][j]) for j in range(n)))
    print('\n'.join(out_lines))

solve()
