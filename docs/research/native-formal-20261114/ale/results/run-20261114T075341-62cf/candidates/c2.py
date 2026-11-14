import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    k = n // m
    stacks = []
    idx = 2
    for i in range(m):
        stacks.append(data[idx:idx+k])
        idx += k
    
    # Track positions of each box
    pos = {}  # box_value -> (stack_idx, position_in_stack)
    for i, stack in enumerate(stacks):
        for j, v in enumerate(stack):
            pos[v] = (i, j)
    
    operations = []
    energy = 0
    
    for value in range(1, n + 1):
        src_i, src_j = pos[value]
        if src_j + 1 < len(stacks[src_i]):
            # Need to move boxes above value
            above = stacks[src_i][src_j+1:]
            
            # Find best destination: prefer empty stacks, then shortest
            # Also consider not creating too many temporary moves
            candidates = []
            for j in range(m):
                if j != src_i:
                    candidates.append((len(stacks[j]), j))
            candidates.sort()
            dest_i = candidates[0][1]
            
            # Move the top part
            moved_box = above[0]
            operations.append((moved_box, dest_i + 1))
            energy += len(above) + 1
            
            # Update state
            stacks[dest_i].extend(above)
            del stacks[src_i][src_j+1:]
            
            # Update positions
            for offset, v in enumerate(above):
                pos[v] = (dest_i, len(stacks[dest_i]) - len(above) + offset)
            
        # Carry out value
        operations.append((value, 0))
        src_i, src_j = pos[value]
        stacks[src_i].pop()
        # Update remaining positions in this stack
        for v in stacks[src_i]:
            new_pos = stacks[src_i].index(v)
            pos[v] = (src_i, new_pos)
    
    # Output
    out = []
    for v, i in operations:
        out.append(f"{v} {i}")
    print("\n".join(out))

solve()