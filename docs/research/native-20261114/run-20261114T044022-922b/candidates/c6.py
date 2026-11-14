import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    sz = n // m
    stacks = []
    idx = 2
    for i in range(m):
        stacks.append(data[idx:idx+sz])
        idx += sz
    
    # position map: value -> (stack_idx, pos_in_stack)
    pos_map = {}
    for i in range(m):
        for j, v in enumerate(stacks[i]):
            pos_map[v] = (i, j)
    
    ops = []
    
    for target in range(1, n + 1):
        src, pos = pos_map[target]
        if pos + 1 < len(stacks[src]):
            above = stacks[src][pos + 1:]
            # choose destination: prefer stack that has the smallest next-needed box at top,
            # or shortest stack; avoid moving boxes that we'll need soon to the bottom of a tall stack
            best_dest = -1
            best_score = None
            for j in range(m):
                if j == src:
                    continue
                # score: prefer shorter stacks, and stacks whose top is a large number (less likely needed soon)
                s_len = len(stacks[j])
                top_val = stacks[j][-1] if s_len > 0 else 9999
                # We want to minimize future cost. A good dest is short and has a large top.
                sc = (s_len, -top_val)  # smaller is better
                if best_score is None or sc < best_score:
                    best_score = sc
                    best_dest = j
            
            ops.append((above[0], best_dest + 1))
            # update stacks
            moved = stacks[src][pos + 1:]
            del stacks[src][pos + 1:]
            stacks[best_dest].extend(moved)
            # update pos_map for moved boxes
            base = len(stacks[best_dest]) - len(moved)
            for k, v in enumerate(moved):
                pos_map[v] = (best_dest, base + k)
        
        ops.append((target, 0))
        # remove target from its stack
        del stacks[src][pos]
        # update pos_map for boxes above target in src (they shifted down by 1)
        for k in range(pos, len(stacks[src])):
            pos_map[stacks[src][k]] = (src, k)
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

solve()
