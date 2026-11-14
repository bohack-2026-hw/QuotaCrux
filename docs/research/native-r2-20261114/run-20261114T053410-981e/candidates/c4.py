import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    if position + 1 < len(stacks[src]):
        above = stacks[src][position + 1:]
        k = len(above)
        if k <= 3:
            # Move all at once to shortest other stack
            candidates = [j for j in range(m) if j != src]
            dest = min(candidates, key=lambda j: (0 if not stacks[j] else 1, len(stacks[j])))
            print(above[0], dest + 1)
            stacks[dest].extend(above)
            del stacks[src][position + 1:]
        else:
            # Split into two groups: top 2 and rest
            # First move the top 2 boxes to one stack
            top_two = above[-2:]
            rest = above[:-2]
            candidates = [j for j in range(m) if j != src]
            # Choose destination for top two: prefer empty, then shortest
            dest1 = min(candidates, key=lambda j: (0 if not stacks[j] else 1, len(stacks[j])))
            print(top_two[0], dest1 + 1)
            stacks[dest1].extend(top_two)
            # Now remove top two from src
            del stacks[src][-2:]
            # Move the rest to another stack
            candidates2 = [j for j in range(m) if j != src]
            dest2 = min(candidates2, key=lambda j: (0 if not stacks[j] else 1, len(stacks[j])))
            if rest:
                print(rest[0], dest2 + 1)
                stacks[dest2].extend(rest)
                del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()