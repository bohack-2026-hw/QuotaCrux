import sys

def main():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    h = n // m
    stacks = []
    idx = 2
    for i in range(m):
        stacks.append(data[idx:idx+h])
        idx += h
    
    # Position tracking: pos[v] = (stack_index, position_in_stack)
    pos = [None] * (n + 1)
    for i in range(m):
        for j, v in enumerate(stacks[i]):
            pos[v] = (i, j)
    
    ops = []
    
    def move_top(src, dest, count):
        """Move top 'count' boxes from src to dest."""
        moved = stacks[src][-count:]
        del stacks[src][-count:]
        stacks[dest].extend(moved)
        for v in moved:
            si, _ = pos[v]
            pos[v] = (dest, len(stacks[dest]) - 1)
        # Update positions of all moved boxes
        for k, v in enumerate(moved):
            pos[v] = (dest, len(stacks[dest]) - count + k)
    
    for value in range(1, n + 1):
        src, p = pos[value]
        if p < len(stacks[src]) - 1:
            # Need to move boxes above value
            above_count = len(stacks[src]) - 1 - p
            # Find best destination: minimize energy cost
            # Energy = above_count + 1
            # But we also want to minimize future costs
            # Choose the shortest stack as destination (excluding src)
            best_dest = None
            min_len = float('inf')
            for j in range(m):
                if j != src and len(stacks[j]) < min_len:
                    min_len = len(stacks[j])
                    best_dest = j
            ops.append((stacks[src][p+1], best_dest + 1))
            move_top(src, best_dest, above_count)
        ops.append((value, 0))
        # Remove value from its stack
        si, pi = pos[value]
        del stacks[si][pi]
        # Update positions of boxes above in this stack
        for k in range(pi, len(stacks[si])):
            v = stacks[si][k]
            pos[v] = (si, k)
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

main()
