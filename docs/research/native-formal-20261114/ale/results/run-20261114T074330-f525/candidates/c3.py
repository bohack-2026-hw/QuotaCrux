import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    h = n // m
    idx = 2
    stacks = []
    for i in range(m):
        stacks.append(data[idx:idx+h])
        idx += h
    
    # Position map: value -> (stack_idx, pos_in_stack)
    pos_map = {}
    for si, stack in enumerate(stacks):
        for pi, v in enumerate(stack):
            pos_map[v] = (si, pi)
    
    ops = []
    total_energy = 0
    
    for value in range(1, n + 1):
        src, pos = pos_map[value]
        if pos + 1 < len(stacks[src]):
            above = stacks[src][pos+1:]
            k = len(above)
            # Choose destination stack to minimize future cost
            # Heuristic: prefer stack where the top of 'above' is smallest,
            # or where adding 'above' keeps the stack's min accessible soon.
            best_dest = -1
            best_score = float('inf')
            for j in range(m):
                if j == src:
                    continue
                # Score: after moving, what's the minimum box that would be blocked?
                # Simpler heuristic: prefer shorter stacks, but also consider
                # whether the moved boxes contain small values that should stay accessible.
                # Use: len(dest) as primary, then check if above[0] is small relative to dest's current top
                score = len(stacks[j])
                # Bonus: if dest is empty or its top > above[-1], it's good
                if len(stacks[j]) == 0:
                    score -= 100  # strongly prefer empty stacks
                else:
                    # If the new top (above[-1]) is smaller than current top, that's bad
                    # because we're burying a potentially needed box
                    if above[-1] < stacks[j][-1]:
                        score += 50
                if score < best_score:
                    best_score = score
                    best_dest = j
            
            ops.append((above[0], best_dest + 1))
            total_energy += k + 1
            
            # Update state
            moved = stacks[src][pos+1:]
            del stacks[src][pos+1:]
            stacks[best_dest].extend(moved)
            # Update pos_map for moved boxes
            for mi, mv in enumerate(moved):
                pos_map[mv] = (best_dest, len(stacks[best_dest]) - len(moved) + mi)
        
        # Carry out value
        ops.append((value, 0))
        # Remove from stack
        del stacks[src][pos]
        # Update pos_map for remaining boxes in src
        for pi in range(pos, len(stacks[src])):
            pos_map[stacks[src][pi]] = (src, pi)
        del pos_map[value]
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

solve()
