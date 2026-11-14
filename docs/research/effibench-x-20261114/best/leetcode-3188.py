import sys

def main():
    data = sys.stdin.buffer.read().decode('ascii')
    lines = data.strip().split('\n')
    n = int(lines[0])
    
    # Parse grid more efficiently
    # The champion is the team with no incoming edges (no team stronger than it)
    # This means for row i, if there's a 1 in column j where j != i, then team j beats team i
    # Actually, grid[i][j] == 1 means team i is stronger than team j
    # Champion has no team b such that grid[b][a] == 1
    # So we need to find a where for all b != a: grid[b][a] == 0
    
    # Alternative: the champion is the one with maximum out-degree
    # Since it's a tournament graph with transitivity, the champion has out-degree n-1
    
    # Let's parse and find the row with all 1s except diagonal
    # Or simply: find index where sum of row equals n-1
    
    best = 0
    best_sum = -1
    
    for i in range(1, n+1):
        line = lines[i]
        # Count 1s in this line
        # Each element is '0' or '1' separated by commas
        # We can count occurrences of '1'
        s = line.count('1')
        if s > best_sum:
            best_sum = s
            best = i - 1
    
    sys.stdout.write(str(best))

main()
