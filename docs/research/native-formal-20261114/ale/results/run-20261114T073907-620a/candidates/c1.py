import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    idx = 0
    n, m = data[idx], data[idx+1]
    idx += 2
    h = n // m
    stacks = []
    for i in range(m):
        stacks.append(data[idx:idx+h])
        idx += h
    
    # position map: box -> (stack_idx, pos_in_stack)
    def build_pos(stacks):
        pos = {}
        for si, st in enumerate(stacks):
            for pi, v in enumerate(st):
                pos[v] = (si, pi)
        return pos
    
    pos = build_pos(stacks)
    ops = []
    
    for value in range(1, n + 1):
        si, pi = pos[value]
        if pi + 1 < len(stacks[si]):
            above = stacks[si][pi+1:]
            k = len(above)
            # choose best destination stack
            best_dest = -1
            best_cost = float('inf')
            for di in range(m):
                if di == si:
                    continue
                # cost heuristic: after moving 'above' to dest di,
                # the boxes in 'above' will need to be removed later.
                # A good dest is one where the top of dest has a large number
                # (so it won't interfere soon) and the stack is short.
                # Also consider: min number in 'above' - if small, we want it accessible soon.
                dest_len = len(stacks[di])
                # Simple heuristic: prefer shorter stacks, and stacks whose top is larger
                top_val = stacks[di][-1] if dest_len > 0 else 0
                min_above = min(above)
                # We want the moved boxes to be easy to access later.
                # If dest is empty or has only large numbers on top, that's good.
                # Cost estimate: dest_len + (top_val if top_val < min_above else 0) * 0.1
                # Actually let's think differently:
                # After moving, the boxes in 'above' sit on top of stack di.
                # When we need to remove them (in order), each removal might require
                # further moves. The key factor is how many boxes are BELOW each box in 'above'
                # within the combined stack, because those must be moved first.
                # But all boxes in 'above' are above each other in the same relative order,
                # so the bottom-most of 'above' has dest_len boxes below it in stack di.
                # This means when removing the bottom-most of 'above', we'd need to move
                # nothing extra (it's already at top of the sub-stack). Wait no - the boxes
                # in 'above' maintain their order, so the first one to be removed from 'above'
                # is min(above) which could be anywhere in the sequence.
                # 
                # Let me use a simpler but effective heuristic:
                # Prefer destinations with fewer boxes, breaking ties by preferring
                # destinations whose current top box has a larger number (less urgent).
                cost = dest_len * 10 + (top_val if dest_len > 0 else 999)
                # Bonus: if the destination is empty, great
                if dest_len == 0:
                    cost -= 50
                if cost < best_cost:
                    best_cost = cost
                    best_dest = di
            
            ops.append((above[0], best_dest + 1))
            stacks[best_dest].extend(above)
            del stacks[si][pi+1:]
            # rebuild pos
            pos = build_pos(stacks)
        
        ops.append((value, 0))
        stacks[si].pop()
        pos = build_pos(stacks)
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

solve()
