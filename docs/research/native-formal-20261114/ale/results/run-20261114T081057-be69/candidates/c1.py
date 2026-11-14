import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    if position + 1 < len(stacks[src]):
        # Choose destination: prefer the stack with the smallest top element (most likely to be carried out soon)
        dest_candidates = []
        for j in range(m):
            if j != src:
                if not stacks[j]:
                    dest_candidates.append((0, j))  # empty stack, highest priority
                else:
                    dest_candidates.append((stacks[j][-1], j))
        dest_candidates.sort()
        dest = dest_candidates[0][1]
        above = stacks[src][position + 1:]
        print(above[0], dest + 1)
        stacks[dest].extend(above)
        del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()
