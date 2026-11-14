import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    h = n // m
    stacks = []
    idx = 2
    for i in range(m):
        stacks.append(data[idx:idx+h])
        idx += h
    
    # position of each box: (stack_index, position_in_stack)
    pos = {}
    for i, s in enumerate(stacks):
        for j, v in enumerate(s):
            pos[v] = (i, j)
    
    ops = []
    energy = 0
    
    def move_boxes(src, start_pos, dest):
        """Move boxes from src stack starting at start_pos to top of dest stack."""
        nonlocal energy
        k = len(stacks[src]) - start_pos
        if k == 0:
            return
        above = stacks[src][start_pos:]
        ops.append((above[0], dest + 1))
        energy += k + 1
        stacks[dest].extend(above)
        del stacks[src][start_pos:]
        # update positions
        for j, v in enumerate(above):
            pos[v] = (dest, len(stacks[dest]) - len(above) + j)
        # update remaining in src
        for j in range(len(stacks[src])):
            pos[stacks[src][j]] = (src, j)
    
    def carry_out(v):
        """Carry out box v which must be on top of its stack and be the smallest remaining."""
        ops.append((v, 0))
        src, p = pos[v]
        assert stacks[src][-1] == v, f"Box {v} not on top of stack {src}"
        stacks[src].pop()
        del pos[v]
        # update positions in src
        for j in range(len(stacks[src])):
            pos[stacks[src][j]] = (src, j)
    
    for value in range(1, n + 1):
        src, p = pos[value]
        if p < len(stacks[src]) - 1:
            # Need to move boxes above value to another stack
            # Find best destination: prefer empty stack, then shortest
            candidates = [j for j in range(m) if j != src]
            # Sort by length, prefer empty
            candidates.sort(key=lambda j: len(stacks[j]))
            dest = candidates[0]
            move_boxes(src, p + 1, dest)
            # After moving, value should now be on top of src
            src, p = pos[value]
        carry_out(value)
    
    print('\n'.join(f'{v} {i}' for v, i in ops))

solve()