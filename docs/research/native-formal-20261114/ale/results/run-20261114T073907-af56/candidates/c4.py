import sys

def main():
    data = sys.stdin.read().split()
    n = int(data[0])
    m = int(data[1])
    grid = []
    idx = 2
    for i in range(n):
        row = list(map(int, data[idx:idx+n]))
        grid.append(row)
        idx += n
    
    # Build adjacency between colors from original map
    adj = [[False]*(m+1) for _ in range(m+1)]
    for i in range(n):
        for j in range(n):
            c = grid[i][j]
            # Check right and down neighbors
            if i < n-1:
                d = grid[i+1][j]
                adj[c][d] = True
                adj[d][c] = True
            if j < n-1:
                d = grid[i][j+1]
                adj[c][d] = True
                adj[d][c] = True
            # Boundary means adjacent to 0
            if i == 0 or i == n-1 or j == 0 or j == n-1:
                adj[c][0] = True
                adj[0][c] = True
    
    # We need to create a new map where each color is connected and adjacencies match.
    # Strategy: place all colors in a compact region, ensuring connectivity.
    # Use a simple approach: assign each color a small block, arrange them so that
    # adjacent colors are next to each other.
    
    # For now, let's try a simple valid solution:
    # Place colors in a spiral or grid pattern in the center.
    # Each color gets at least 1 cell. We'll use 1 cell per color for simplicity,
    # but they must be connected (single cell is trivially connected).
    # The challenge is arranging them so that adjacencies match.
    
    # A simpler approach: use the original positions but shrink.
    # Actually, let's just output the original grid as-is for now (valid but score=1).
    # Wait, the original grid has no 0s inside, so E=0, score=1.
    # We need to introduce 0s to increase E.
    
    # Let's try: keep each color as a single pixel, arranged in a 10x10 grid in the center.
    # Colors 1-100 placed in a 10x10 block starting at (20,20).
    # This gives E = 2500 - 100 = 2400, score = 2401.
    # But we need to check if adjacencies can be satisfied.
    
    # For a first attempt, let's just output the original grid (safe, score=1).
    out = []
    for i in range(n):
        out.append(' '.join(str(grid[i][j]) for j in range(n)))
    print('\n'.join(out))

main()