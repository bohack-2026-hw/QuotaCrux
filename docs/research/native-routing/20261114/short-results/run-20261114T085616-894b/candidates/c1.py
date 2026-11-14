import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    if position + 1 < len(stacks[src]):
        # 选择目标堆：优先选择空堆，其次选择最短的堆
        empty_stacks = [j for j in range(m) if j != src and len(stacks[j]) == 0]
        if empty_stacks:
            dest = empty_stacks[0]
        else:
            dest = min((j for j in range(m) if j != src), key=lambda j: len(stacks[j]))
        above = stacks[src][position + 1:]
        print(above[0], dest + 1)
        stacks[dest].extend(above)
        del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()
