import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    if position + 1 < len(stacks[src]):
        # Choose destination: prefer empty stacks, then stack with largest top element
        candidates = [j for j in range(m) if j != src]
        # Score each candidate: empty stacks are best, then largest top
        def score(j):
            if not stacks[j]:
                return (0, -len(stacks[j]))  # Empty stacks first
            else:
                return (1, -stacks[j][-1])  # Largest top element first
        dest = min(candidates, key=score)
        above = stacks[src][position + 1:]
        print(above[0], dest + 1)
        stacks[dest].extend(above)
        del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()
