import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    if position + 1 < len(stacks[src]):
        above = stacks[src][position + 1:]
        min_above = min(above)
        # First try to find a stack whose top is greater than min_above
        candidates = []
        for j in range(m):
            if j == src:
                continue
            if not stacks[j]:
                candidates.append((0, j))  # Empty stack is best
            elif stacks[j][-1] > min_above:
                candidates.append((len(stacks[j]), j))
        if candidates:
            dest = min(candidates)[1]
        else:
            # No suitable stack, pick the shortest one
            dest = min((j for j in range(m) if j != src), key=lambda j: len(stacks[j]))
        print(above[0], dest + 1)
        stacks[dest].extend(above)
        del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()
