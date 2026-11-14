import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    if position + 1 < len(stacks[src]):
        above = stacks[src][position + 1:]
        # Find the destination stack that minimizes future cost.
        # Heuristic: choose a stack where the moved boxes are already sorted and have small numbers,
        # or just pick the shortest stack as before but with tie-breaking by top element.
        best_dest = None
        best_key = None
        for j in range(m):
            if j == src:
                continue
            # Prefer shorter stacks; break ties by smaller top box (if any)
            key = (len(stacks[j]), stacks[j][-1] if stacks[j] else float('inf'))
            if best_key is None or key < best_key:
                best_key = key
                best_dest = j
        print(above[0], best_dest + 1)
        stacks[best_dest].extend(above)
        del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()
