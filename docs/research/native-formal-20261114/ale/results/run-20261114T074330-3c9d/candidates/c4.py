import sys

def main():
    input_data = sys.stdin.read().split()
    n = int(input_data[0])
    m = int(input_data[1])
    grid = []
    idx = 2
    for i in range(n):
        row = []
        for j in range(n):
            row.append(int(input_data[idx]))
            idx += 1
        grid.append(row)
    
    # Output the same grid as input (trivial solution)
    for i in range(n):
        print(' '.join(map(str, grid[i])))

if __name__ == '__main__':
    main()