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
    
    # position[v] = (stack_idx, pos_in_stack)
    pos = {}
    for i in range(m):
        for j, v in enumerate(stacks[i]):
            pos[v] = (i, j)
    
    ops = []
    
    for value in range(1, n + 1):
        src, p = pos[value]
        if p < len(stacks[src]) - 1:
            # Need to move boxes above value to another stack
            above = stacks[src][p+1:]
            # Choose destination: prefer the stack with the smallest minimum remaining box
            # that is not src, and has space considerations
            best_dest = None
            best_score = None
            for j in range(m):
                if j == src:
                    continue
                # Score: we want a dest where the top boxes are "small" so they get removed soon
                # Actually we want dest where after adding 'above', the boxes in 'above' can be
                # removed as quickly as possible.
                # Key insight: if dest stack's current top boxes are all > min(above), then
                # when we remove from dest, we'll hit 'above' boxes sooner.
                # Better: pick dest with fewest boxes (least interference)
                # Or: pick dest whose existing boxes are all larger than min(above)
                # so above boxes become accessible quickly.
                
                # Strategy: minimize the number of boxes that will need to be moved again.
                # If we put 'above' on stack j, the boxes in 'above' will be on top.
                # They can be removed one by one (if they're the smallest remaining) or
                # moved again. To minimize future moves, put them on a stack where
                # the existing boxes are all > max(above) won't help since above is on top.
                # Actually above is placed ON TOP, so it's always accessible first.
                # The issue is: when we need to remove a box from below 'above' in dest,
                # we'd have to move 'above' again. But since above is on top, this only
                # happens if some box in the original part of dest needs removal before
                # all of 'above' is gone.
                
                # Simple heuristic: pick the shortest stack (not src)
                score = len(stacks[j])
                if best_score is None or score < best_score:
                    best_score = score
                    best_dest = j
            
            ops.append((above[0], best_dest + 1))
            # Update positions
            old_len = len(stacks[best_dest])
            stacks[best_dest].extend(above)
            for k, v in enumerate(above):
                pos[v] = (best_dest, old_len + k)
            del stacks[src][p+1:]
        
        # Remove value
        ops.append((value, 0))
        # Update: all boxes above position p in src shift down (but we already removed them)
        # Just remove value at position p
        del stacks[src][p]
        # Update positions for remaining boxes in src
        for k in range(p, len(stacks[src])):
            pos[stacks[src][k]] = (src, k)
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

solve()
