import sys

def main():
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    m = int(data[1])
    grid = []
    idx = 2
    for i in range(n):
        row = list(map(int, data[idx:idx+n]))
        grid.append(row)
        idx += n
    
    # For now, just output the original grid as a valid solution
    # This ensures correctness but doesn't optimize the score
    out_lines = []
    for i in range(n):
        out_lines.append(' '.join(str(x) for x in grid[i]))
    print('\n'.join(out_lines))

if __name__ == '__main__':
    main()
