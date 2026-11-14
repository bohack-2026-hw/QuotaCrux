import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    idx = 2
    stacks = []
    for i in range(m):
        stacks.append(data[idx:idx + n // m])
        idx += n // m
    
    # Build position map: value -> (stack_index, position_in_stack)
    pos_map = {}
    for i, stack in enumerate(stacks):
        for j, v in enumerate(stack):
            pos_map[v] = (i, j)
    
    ops = []
    
    for value in range(1, n + 1):
        src, position = pos_map[value]
        
        if position < len(stacks[src]):
            # Need to move boxes above value
            above = stacks[src][position + 1:]
            if above:
                # Choose best destination stack
                # We want to minimize total energy. Moving k boxes costs k+1.
                # After moving, we can carry out 'value' for free.
                # Then the boxes in 'above' are on top of dest stack.
                # 
                # Strategy: pick the stack that will let us extract the most boxes next
                # without additional moves. That is, a stack where the moved boxes
                # form a contiguous ascending sequence from the top.
                # 
                # Actually, let's think about it differently:
                # The cost is always k+1 regardless of destination.
                # So the key is to choose destination such that future operations
                # are minimized.
                # 
                # A good heuristic: move to the shortest stack (not src) to keep things balanced,
                # but also consider which boxes are in 'above' - if they're consecutive
                # and in order, putting them on a stack where they can be extracted easily helps.
                # 
                # Better approach: look at what's below each potential dest stack.
                # If we put 'above' on stack j, then the top of stack j becomes above[-1].
                # The boxes in 'above' can be extracted in reverse order from top.
                # If above contains values that are consecutive and increasing from bottom to top,
                # then after extraction of lower boxes, they'll be ready.
                # 
                # Simplest improvement: among all dest != src, pick the one with minimum length.
                # This keeps stacks balanced and reduces future move sizes.
                
                best_dest = None
                best_score = None
                for j in range(m):
                    if j == src:
                        continue
                    # Score: prefer shorter stacks, and stacks where the top box
                    # is smaller than min(above) so that above boxes can be extracted soon
                    score = len(stacks[j])
                    # Bonus if the top of dest is less than the smallest in above
                    if stacks[j]:
                        top_val = stacks[j][-1]
                        if top_val < min(above):
                            score -= 1000  # strong preference
                    else:
                        score -= 2000  # empty stack is great
                    if best_score is None or score < best_score:
                        best_score = score
                        best_dest = j
                
                dest = best_dest
                k = len(above)
                ops.append((above[0], dest + 1))
                
                # Update state
                stacks[dest].extend(above)
                del stacks[src][position + 1:]
                
                # Update pos_map for moved boxes
                for offset, v in enumerate(above):
                    pos_map[v] = (dest, len(stacks[dest]) - len(above) + offset)
                # Update pos_map for remaining boxes in src
                for j in range(position + 1, len(stacks[src])):
                    pos_map[stacks[src][j]] = (src, j)
        
        # Carry out value
        ops.append((value, 0))
        # Remove from stack
        stacks[src].pop()
        # Update pos_map for boxes below
        for j in range(len(stacks[src])):
            pos_map[stacks[src][j]] = (src, j)
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    print("\n".join(out))

solve()
