import sys

def main():
    input_data = sys.stdin.read().splitlines()
    if not input_data:
        return
    
    n_m = list(map(int, input_data[0].split()))
    n, m = n_m[0], n_m[1]
    
    # Read the grid
    grid = []
    for i in range(n):
        row = list(map(int, input_data[i+1].split()))
        grid.append(row)
    
    # Build adjacency graph between colors
    color_adj = {c: set() for c in range(m+1)}
    
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check right and down neighbors to avoid duplicates
            if i < n-1:
                d = grid[i+1][j]
                if c != d:
                    color_adj[c].add(d)
                    color_adj[d].add(c)
            if j < n-1:
                d = grid[i][j+1]
                if c != d:
                    color_adj[c].add(d)
                    color_adj[d].add(c)
    
    # Add boundary adjacencies with color 0
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                color_adj[c].add(0)
                color_adj[0].add(c)
    
    # Now we need to create a new map that preserves these adjacencies
    # Strategy: Place each color as a single tile (or connected group) in the grid
    # We'll use a simple approach: place colors in a snake pattern
    
    # First, let's figure out which colors are adjacent to 0 (boundary colors)
    boundary_colors = set(color_adj[0])
    
    # For simplicity, let's try to place each color as a single cell
    # This is only valid if no two adjacent colors both need multiple cells
    # Let's check if this is possible
    
    # Actually, let me think about this differently.
    # The key insight is that we want to minimize the number of 0 cells.
    # So we want to maximize the number of non-zero cells.
    
    # Simple approach: Try to fit all m colors into the grid as single cells,
    # arranged so that adjacent colors are next to each other.
    
    # Let's build the adjacency graph excluding 0
    adj_graph = {c: set() for c in range(1, m+1)}
    for c in range(1, m+1):
        for d in color_adj[c]:
            if d >= 1:
                adj_graph[c].add(d)
    
    # Try to arrange colors in a grid pattern
    # Use a greedy approach: start with a color, then add adjacent colors
    
    # For now, let's just output the original grid as a baseline
    # This guarantees correctness but doesn't optimize the score
    for i in range(n):
        print(' '.join(map(str, grid[i])))

if __name__ == '__main__':
    main()