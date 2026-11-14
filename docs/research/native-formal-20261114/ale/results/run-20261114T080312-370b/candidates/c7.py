import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    if position + 1 < len(stacks[src]):
        above = stacks[src][position + 1:]
        # Choose destination that avoids boxes with small numbers (soon to be removed)
        def score_dest(j):
            if j == src:
                return float('inf')
            s = stacks[j]
            # Penalty: count of boxes in dest that are smaller than current value+some margin
            penalty = sum(1 for x in s if x <= value + 5)
            # Combine penalty and length: prefer low penalty, then short
            return (penalty, len(s))
        dest = min(range(m), key=score_dest)
        print(above[0], dest + 1)
        stacks[dest].extend(above)
        del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()
