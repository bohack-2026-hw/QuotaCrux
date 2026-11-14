import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]

# Precompute position of each box: pos[v] = (stack_idx, height_in_stack)
pos = {}
for i, stack in enumerate(stacks):
    for j, v in enumerate(stack):
        pos[v] = (i, j)

ops = []
carried_out = set()

for value in range(1, n + 1):
    src, p = pos[value]
    # Check if there are boxes above value in its stack
    if p + 1 < len(stacks[src]):
        # Need to move the block above value
        # Choose destination: prefer stack whose minimum remaining box has largest value
        # (i.e., least likely to need extraction soon)
        best_dest = -1
        best_score = None
        for j in range(m):
            if j == src:
                continue
            # Find minimum remaining box in stack j
            min_remaining = None
            for box in stacks[j]:
                if box not in carried_out:
                    if min_remaining is None or box < min_remaining:
                        min_remaining = box
            if min_remaining is None:
                # Stack is empty (all carried out) - very good target
                score = (float('inf'), -len(stacks[j]))
            else:
                score = (min_remaining, -len(stacks[j]))
            if best_score is None or score > best_score:
                best_score = score
                best_dest = j
        
        above = stacks[src][p + 1:]
        ops.append((above[0], best_dest + 1))
        # Update positions for moved boxes
        for k, box in enumerate(above):
            pos[box] = (best_dest, len(stacks[best_dest]) + k)
        stacks[best_dest].extend(above)
        del stacks[src][p + 1:]
    
    ops.append((value, 0))
    carried_out.add(value)
    stacks[src].pop()

for v, i in ops:
    print(v, i)
