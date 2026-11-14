import sys

def solve():
    input_data = sys.stdin.read().splitlines()
    n, m = map(int, input_data[0].split())
    grid = [list(map(int, line.split())) for line in input_data[1:1+n]]
    
    # Initialize result grid with all zeros
    result = [[0]*n for _ in range(n)]
    
    # Place each color in a connected way
    for c in range(1, m+1):
        cells = [(i,j) for i in range(n) for j in range(n) if grid[i][j] == c]
        if not cells:
            continue
        
        # Start from the first cell and grow the region
        start_i, start_j = cells[0]
        result[start_i][start_j] = c
        visited = {(start_i, start_j)}
        queue = [(start_i, start_j)]
        
        while queue:
            ci, cj = queue.pop(0)
            for di, dj in [(0,1),(0,-1),(1,0),(-1,0)]:
                ni, nj = ci + di, cj + dj
                if 0 <= ni < n and 0 <= nj < n and (ni,nj) not in visited and grid[ni][nj] == c:
                    result[ni][nj] = c
                    visited.add((ni,nj))
                    queue.append((ni,nj))
    
    # Output the result
    for row in result:
        print(' '.join(map(str, row)))

solve()