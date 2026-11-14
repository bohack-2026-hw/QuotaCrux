import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    if position + 1 < len(stacks[src]):
        above = stacks[src][position + 1:]
        # Choose destination stack that minimizes future moves
        # Prefer stacks with more large-numbered boxes (less likely to be moved soon)
        def score_dest(j):
            if j == src:
                return float('inf')
            s = stacks[j]
            if not s:
                return -len(s)  # empty is good
            # Sum of box numbers in dest stack - larger means less urgent
            return -sum(s)
        dest = min(range(m), key=score_dest)
        print(above[0], dest + 1)
        stacks[dest].extend(above)
        del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()
