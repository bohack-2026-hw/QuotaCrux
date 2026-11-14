import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    it = iter(data)
    n, m = next(it), next(it)
    stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
    
    # Track position of each box: pos[box] = (stack_idx, index_in_stack)
    pos = {}
    for i, stack in enumerate(stacks):
        for j, b in enumerate(stack):
            pos[b] = (i, j)
    
    operations = []
    
    for value in range(1, n + 1):
        src, idx = pos[value]
        if idx + 1 < len(stacks[src]):
            # Need to move boxes above value
            above = stacks[src][idx + 1:]
            # Choose destination that minimizes energy and maximizes future benefit
            best_dest = -1
            best_score = float('inf')
            for dest in range(m):
                if dest == src:
                    continue
                # Energy cost is len(above) + 1
                cost = len(above) + 1
                # After moving, check how many consecutive boxes from the top we can extract
                # The new top of dest will be above[-1], then above[-2], etc.
                # We want to maximize the number of boxes we can immediately take out after this move
                # Actually, let's think about it differently:
                # After moving 'above' to dest, the top of dest becomes above[-1]
                # If above[-1] is the smallest remaining box, we can take it out for free
                # Let's count how many boxes from the end of 'above' are consecutive in the extraction order
                
                # Better heuristic: choose the destination where the top box has the largest label
                # (so it stays there longer and doesn't block us), or where we can extract more
                
                # Simple approach: minimize the length of the destination stack after adding
                # This keeps stacks balanced and reduces future moves
                new_len = len(stacks[dest]) + len(above)
                score = new_len * 1000 + cost  # Prefer shorter stacks
                if score < best_score:
                    best_score = score
                    best_dest = dest
            
            operations.append((above[0], best_dest + 1))
            
            # Update positions
            for k, b in enumerate(above):
                pos[b] = (best_dest, len(stacks[best_dest]) + k)
            stacks[best_dest].extend(above)
            del stacks[src][idx + 1:]
        
        operations.append((value, 0))
        
        # Remove value from its stack
        stacks[src].pop()
        # Update positions for all boxes in src stack above idx (already removed)
        # Actually we already handled that. Just remove value's position
        del pos[value]
        # Update positions for boxes below value in src (they shifted down by 1? No, they didn't shift)
        # Wait, when we pop from the end, only the last element is removed. But value might not be at the end!
        # Let me re-examine: value is at position idx in stacks[src]. We remove everything above it first,
        # so now value is at the top. Then we pop it.
        # After removing 'above', stacks[src] has elements [0..idx], and value is at idx (the last).
        # So popping removes value correctly.
        # But we need to update positions for boxes that were above value - already done.
        # Boxes below value don't change position.
    
    out = []
    for v, i in operations:
        out.append(f"{v} {i}")
    print("\n".join(out))

solve()