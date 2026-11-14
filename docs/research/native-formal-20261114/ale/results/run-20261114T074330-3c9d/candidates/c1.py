import sys

def main():
    input_data = sys.stdin.read().split()
    n = int(input_data[0])
    m = int(input_data[1])
    
    # Read the grid
    grid = []
    idx = 2
    for i in range(n):
        row = list(map(int, input_data[idx:idx+n]))
        grid.append(row)
        idx += n
    
    # Build adjacency graph between colors (including color 0 for outside)
    # adj[c][d] = True if color c and d are adjacent in original map
    adj = [[False]*(m+1) for _ in range(m+1)]
    
    # Check boundary for color 0 adjacency
    for i in range(n):
        if grid[i][0] != 0:
            adj[grid[i][0]][0] = True
            adj[0][grid[i][0]] = True
        if grid[i][n-1] != 0:
            adj[grid[i][n-1]][0] = True
            adj[0][grid[i][n-1]] = True
    for j in range(n):
        if grid[0][j] != 0:
            adj[grid[0][j]][0] = True
            adj[0][grid[0][j]] = True
        if grid[n-1][j] != 0:
            adj[grid[n-1][j]][0] = True
            adj[0][grid[n-1][j]] = True
    
    # Check internal adjacencies
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            if i+1 < n:
                d = grid[i+1][j]
                if c != d:
                    adj[c][d] = True
                    adj[d][c] = True
            if j+1 < n:
                d = grid[i][j+1]
                if c != d:
                    adj[c][d] = True
                    adj[d][c] = True
    
    # Now we need to create a new map where each color is connected
    # and adjacencies are preserved.
    # Strategy: Place each color as a single cell or small connected block.
    # We'll use a greedy approach: try to place colors one by one.
    
    # First, let's figure out which colors need to be on the boundary (adjacent to 0)
    boundary_colors = set()
    for c in range(1, m+1):
        if adj[c][0]:
            boundary_colors.add(c)
    
    # Simple approach: place all colors in a compact arrangement.
    # Each color gets at least 1 cell. Colors that are adjacent must touch.
    # This is essentially a graph embedding problem.
    
    # For now, let's just output the original grid (which is valid but has E=0, score=1)
    # Actually wait - the original grid might not have color 0 cells inside.
    # Let me check: the problem says outside is color 0, but inside all cells are 1..m.
    # So in the original map, there are NO cells with color 0.
    # But in our created map, we can have color 0 cells.
    
    # The key insight: we need to minimize non-zero cells while maintaining connectivity
    # and adjacency relationships.
    
    # Let's think about this differently. We have m colors, each needs at least 1 cell.
    # Total cells = n*n = 2500. We want to maximize zeros.
    
    # A simple valid solution: put each color in exactly one cell, arranged so that
    # adjacent colors in the graph are placed next to each other.
    # But we also need each color to be connected (trivially true with 1 cell).
    # And color 0 must be connected (the rest of the grid).
    
    # The challenge is arranging m=100 colored cells in a 50x50 grid such that:
    # 1. Adjacent colors in the graph are edge-adjacent in the grid
    # 2. Color 0 fills the rest and is connected
    
    # This is like finding a planar embedding of the adjacency graph.
    # Since the original map is on a grid, the adjacency graph is planar.
    
    # Let's try a simple approach: use BFS/DFS ordering from the original positions.
    # Take one representative cell for each color from the original grid,
    # then arrange them in a compact cluster.
    
    # Get representative positions
    reps = {}
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            if c not in reps:
                reps[c] = (i, j)
    
    # Sort colors by their position to maintain spatial coherence
    sorted_colors = sorted(range(1, m+1), key=lambda c: (reps[c][0], reps[c][1]))
    
    # Place them in a compact region starting from top-left
    result = [[0]*n for _ in range(n)]
    pos = 0
    for c in sorted_colors:
        r = pos // n
        col = pos % n
        result[r][col] = c
        pos += 1
    
    # Output
    print('\n'.join(' '.join(map(str, row)) for row in result))

main()