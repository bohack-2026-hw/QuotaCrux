import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    # Move boxes above value one by one from top to bottom
    while position + 1 < len(stacks[src]):
        # The box at the top of the portion above value
        top_box = stacks[src][-1]
        # Choose destination: prefer empty stacks, then shortest
        candidates = [j for j in range(m) if j != src]
        dest = min(candidates, key=lambda j: (0 if not stacks[j] else 1, len(stacks[j])))
        print(top_box, dest + 1)
        stacks[dest].append(top_box)
        stacks[src].pop()
    print(value, 0)
    stacks[src].pop()