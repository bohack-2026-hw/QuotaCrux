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
    
    # Build adjacency graph between colors
    adj = set()
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            if i + 1 < n:
                d = grid[i+1][j]
                if c != d:
                    adj.add((min(c,d), max(c,d)))
            if j + 1 < n:
                d = grid[i][j+1]
                if c != d:
                    adj.add((min(c,d), max(c,d)))
    
    # For each color, find its cells and determine which boundary it touches
    color_cells = {c: [] for c in range(1, m+1)}
    color_boundary = {c: set() for c in range(1, m+1)}
    
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            color_cells[c].append((i,j))
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                color_boundary[c].add((i,j))
    
    # We need to place each color's cells such that:
    # 1. Each color is connected
    # 2. Adjacency relationships are preserved
    # 3. Minimize number of 0 cells
    
    # Strategy: Use a simple approach where we try to pack colors into the grid
    # Start with all 0s, then place colors one by one
    
    result = [[0]*n for _ in range(n)]
    
    # Determine order of colors - maybe by size or some heuristic
    # For now, just process in order 1..m
    
    # A simpler approach: keep the original grid but merge some regions
    # Actually, let's just output the original grid as a valid solution
    # This gives E = number of 0s in original = 0 (since all cells have color 1..m)
    # Wait, the problem says outside is color 0, but inside all cells have color 1..m
    # So E would be 0, score = 1
    
    # Let me re-read: "Let E be the total number of squares of color 0 in the created map"
    # The input has no 0s inside, so if we output the same grid, E=0, score=1
    
    # To improve, we need to create a map with MORE 0s? No wait...
    # Score = E + 1, maximize score means maximize E
    # But we want fewer tiles... I think I misread.
    
    # Re-reading: "create a map using as few tiles as possible" - this means minimize non-zero tiles
    # But scoring says maximize E+1 where E is number of 0s
    # So maximizing E = minimizing non-zero tiles = using fewer colored tiles
    
    # So we want to represent the adjacency structure with as few colored tiles as possible
    
    # Simple feasible solution: use the original grid (all 2500 cells colored)
    # This gives E=0, score=1 per case
    
    # Better: try to compress. Each color needs at least 1 tile.
    # Minimum possible: m tiles (one per color) if they can all be adjacent correctly
    
    # For now, output original grid as baseline
    print('\n'.join(' '.join(map(str,row)) for row in grid))

solve()
