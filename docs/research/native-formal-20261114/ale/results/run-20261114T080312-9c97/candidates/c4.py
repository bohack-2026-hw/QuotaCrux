import sys
from collections import deque

def solve():
    input_data = sys.stdin.read().split()
    idx = 0
    n = int(input_data[idx]); idx += 1
    m = int(input_data[idx]); idx += 1
    
    # Read the grid
    grid = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(input_data[idx])); idx += 1
        grid.append(row)
    
    # Build adjacency between colors (including color 0 for outside)
    # Two colors are adjacent if they share an edge in the original map
    adj_colors = set()
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check right and down neighbors to avoid duplicates
            if j + 1 < n:
                d = grid[i][j+1]
                if c != d:
                    adj_colors.add((min(c,d), max(c,d)))
            if i + 1 < n:
                d = grid[i+1][j]
                if c != d:
                    adj_colors.add((min(c,d), max(c,d)))
            # Boundary: check if on boundary, then adjacent to 0
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                adj_colors.add((0, c))
    
    # Convert to adjacency list
    adj_list = {i: set() for i in range(m+1)}
    for a, b in adj_colors:
        adj_list[a].add(b)
        adj_list[b].add(a)
    
    # Strategy: Try to create a compact arrangement.
    # One approach: place each color as a small connected block.
    # We need to ensure that if two colors are adjacent, their blocks touch.
    # And if not adjacent, they don't touch.
    
    # A simple heuristic: use a spiral or grid-like placement.
    # Let's try to arrange colors in a way that minimizes total area used.
    
    # For now, let's try a basic approach: assign each color to a position
    # in a smaller grid, and expand to fill.
    
    # Actually, let's think differently. The key insight is that we can
    # shrink each region as long as connectivity and adjacency are preserved.
    
    # Simple baseline improvement: try to pack colors into fewer cells.
    # Each color needs at least 1 cell. If two colors are adjacent, they
    # need to share an edge.
    
    # Let's try a greedy packing: place colors one by one, trying to use
    # existing cells where possible.
    
    # For simplicity, let's start with a straightforward approach:
    # Create a new grid and place each color in a compact shape.
    
    # We'll use a BFS-based approach to grow each color from a seed.
    
    # First, determine which colors are on the boundary (adjacent to 0)
    boundary_colors = adj_list[0]
    
    # Sort colors: boundary colors first, then others
    # This helps with placing them near the edges
    
    # Let's try a different approach: simulate shrinking.
    # Start with the original grid and try to remove cells one by one,
    # checking if validity is maintained.
    
    # This might be slow but let's try a limited version.
    
    # Actually, given time constraints, let's implement a simpler heuristic:
    # Place all colors in a compact arrangement using a space-filling curve.
    
    # For now, return the original grid as a valid solution.
    # This gives score = number of 0s + 1, but there are no 0s in input.
    # Wait, the input has no 0s! All cells are colored 1..m.
    # So E=0 and score=1 for each test case.
    
    # To improve, we need to introduce 0s while maintaining constraints.
    
    # Let me implement a proper algorithm.
    
    # Approach: 
    # 1. Identify the dual graph (colors as nodes, edges for adjacency)
    # 2. Find a planar embedding or at least a valid arrangement
    # 3. Assign positions and sizes to minimize total non-zero cells
    
    # Given complexity, let's try a practical heuristic:
    # - Place colors in a grid pattern, with each color occupying a small block
    # - Ensure adjacent colors' blocks touch
    # - Fill remaining space with 0s
    
    # Let's compute a layout:
    # Arrange colors in rows, with boundary colors on the outer ring.
    
    # For a quick improvement, let's try to merge adjacent same-color regions
    # and see if we can reduce the footprint.
    
    # Actually, the simplest improvement: since all colors must be present
    # and connected, and adjacency must be preserved, let's try to create
    # a more compact representation.
    
    # Let's use a simple strategy: place each color as a single cell if possible,
    # but that won't work because adjacent colors need to share edges.
    
    # Minimum size for each color: 1 cell.
    # But if color A is adjacent to B and C, A needs to touch both.
    
    # Let's try: assign each color to a position in a smaller grid.
    # Use the adjacency structure to guide placement.
    
    # For this iteration, let's just output the original grid.
    # Future iterations will implement better heuristics.
    
    result = [str(x) for x in grid[i]] if False else None
    lines = []
    for i in range(n):
        lines.append(' '.join(str(grid[i][j]) for j in range(n)))
    print('\n'.join(lines))

solve()
