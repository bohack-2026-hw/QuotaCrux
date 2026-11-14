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
        # Choose destination: prefer stack with largest top value (so min_above < top_value)
        # Among those, prefer shorter stacks
        best_dest = -1
        best_score = float('-inf')
        for j in range(m):
            if j == src:
                continue
            if not stacks[j]:
                score = 0  # empty stack, neutral
            else:
                top_val = stacks[j][-1]
                # If min_above < top_val, good (min_above will be taken before top_val)
                # Score: larger top_val is better, but also consider stack height
                score = top_val * 10 - len(stacks[j])
            if score > best_score:
                best_score = score
                best_dest = j
        dest = best_dest
        print(above[0], dest + 1)
        stacks[dest].extend(above)
        del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()
