import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    if position + 1 < len(stacks[src]):
        above = stacks[src][position + 1:]
        # Choose destination: prefer empty stacks, then shortest stacks
        candidates = [j for j in range(m) if j != src]
        # Sort by: (is_empty desc, length asc)
        def score(j):
            if not stacks[j]:
                return (0, len(stacks[j]))
            else:
                return (1, len(stacks[j]))
        dest = min(candidates, key=score)
        print(above[0], dest + 1)
        stacks[dest].extend(above)
        del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()
