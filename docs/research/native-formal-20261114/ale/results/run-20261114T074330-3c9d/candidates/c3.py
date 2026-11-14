import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    
    n = int(input_data[0])
    m = int(input_data[1])
    
    # Parse the grid
    grid = []
    idx = 2
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(input_data[idx]))
            idx += 1
        grid.append(row)
    
    # Find adjacency relationships between colors
    adj = [[False] * (m + 1) for _ in range(m + 1)]
    
    for i in range(n):
        for j in range(n):
            c1 = grid[i][j]
            # Check right neighbor
            if j + 1 < n:
                c2 = grid[i][j + 1]
                adj[c1][c2] = True
                adj[c2][c1] = True
            # Check down neighbor
            if i + 1 < n:
                c2 = grid[i + 1][j]
                adj[c1][c2] = True
                adj[c2][c1] = True
    
    # Mark boundary adjacencies with color 0
    for i in range(n):
        adj[grid[i][0]][0] = True
        adj[0][grid[i][0]] = True
        adj[grid[i][n-1]][0] = True
        adj[0][grid[i][n-1]] = True
    
    for j in range(n):
        adj[grid[0][j]][0] = True
        adj[0][grid[0][j]] = True
        adj[grid[n-1][j]][0] = True
        adj[0][grid[n-1][j]] = True
    
    # For now, just output the original grid as a valid solution
    # This ensures correctness while we develop better algorithms
    result = [str(grid[i][j]) for i in range(n) for j in range(n)]
    print(' '.join(result[:n]))
    for i in range(1, n):
        print(' '.join(result[i*n:(i+1)*n]))

solve()
