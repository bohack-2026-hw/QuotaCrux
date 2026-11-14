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
    
    # Position of each box: (stack_index, position_in_stack)
    pos = {}
    for i in range(m):
        for j, v in enumerate(stacks[i]):
            pos[v] = (i, j)
    
    operations = []
    
    for value in range(1, n + 1):
        src, spos = pos[value]
        if spos + 1 < len(stacks[src]):
            # Need to move boxes above value to another stack
            # For each candidate destination stack, compute how many boxes smaller than value are in that stack
            # After moving, value will be at position (len(dest_stack) + spos + 1 - 1) = len(dest_stack) + spos
            # But actually, the boxes above value are moved, so value stays in src.
            # Wait, no. We move boxes ABOVE value to dest. Value stays in src.
            # Then we need to remove value from src. But value must be at top of src.
            # So after moving boxes above value, value is at top of src, and we can carry it out.
            # 
            # Actually, let me re-read the problem.
            # Operation 1: Choose box v, remove v and all boxes above it from current stack, move to top of another stack.
            # So we're moving v AND everything above v.
            # 
            # Wait, I think I misread. Let me re-read.
            # "Remove box v and all boxes above it from the current stack and move them to the top of another stack"
            # So we move v and everything above v. That means v leaves its original stack.
            # 
            # So the strategy should be:
            # To carry out box `value`, it must be at the top of some stack.
            # If it's not at the top, we need to move it (and everything above it) to another stack.
            # But wait, if we move value and everything above it, then value is no longer in its original stack.
            # And we want to carry out value next.
            # 
            # Hmm, actually looking at c0's code more carefully:
            # It finds where value is, and if there are boxes above it, it moves those boxes (not including value) to another stack.
            # Wait no, c0 does: above = stacks[src][position + 1:], then moves above[0] (the box just above value) to dest.
            # This moves the box above value and everything above THAT box, which is all boxes above value.
            # So value becomes the top of src, and then it carries out value.
            # 
            # OK so the approach is correct. Now let me think about the better strategy.
            # 
            # When we need to move boxes above `value` from src to some dest:
            # The boxes being moved are stacks[src][spos+1:]
            # After moving, these boxes go on top of stacks[dest].
            # 
            # The key insight: we want to minimize future cost. A good heuristic is to move the boxes to a stack where they won't block other small boxes for long.
            # 
            # Alternative approach: instead of always moving to the shortest stack, consider which destination minimizes the number of times we'll need to move these boxes again.
            # 
            # Actually, a simpler improvement: when choosing dest, prefer stacks where the top box is larger than the boxes we're moving. This way, the moved boxes will be on top and can be accessed sooner.
            # 
            # Even better: think about it as - we want to place the moved boxes such that the smallest among them will be carried out soonest.
            # 
            # Let me try a different approach: for each candidate dest, simulate what happens and count total energy.
            # But that might be too expensive.
            # 
            # Let me try: choose dest that minimizes the number of boxes in dest that are smaller than the minimum of the boxes being moved.
            # Because those boxes would need to be removed before the moved boxes can be accessed.
            # 
            # Actually, the simplest good heuristic: move to the stack where the top element is largest (so our boxes go on top of a large element and stay accessible).
            # Or move to an empty stack if possible.
            # 
            # Let me try: among all dest != src, pick the one with the largest top element (or empty). This way our boxes sit on top of a big number and won't interfere.
            
            min_moved = min(stacks[src][spos+1:])
            best_dest = -1
            best_key = None
            for j in range(m):
                if j == src:
                    continue
                if len(stacks[j]) == 0:
                    key = (0, 0)  # empty stack is great
                else:
                    top = stacks[j][-1]
                    # Count boxes in stack j that are smaller than min_moved
                    # These would block access to our moved boxes
                    blocking = sum(1 for x in stacks[j] if x < min_moved)
                    key = (blocking, len(stacks[j]))
                if best_key is None or key < best_key:
                    best_key = key
                    best_dest = j
            
            above = stacks[src][spos+1:]
            operations.append((above[0], best_dest + 1))
            stacks[best_dest].extend(above)
            del stacks[src][spos+1:]
            # Update positions for moved boxes
            for k, v in enumerate(above):
                pos[v] = (best_dest, len(stacks[best_dest]) - len(above) + k)
        
        # Carry out value
        operations.append((value, 0))
        del stacks[src][spos]
        # Update positions for remaining boxes in src
        for k in range(spos, len(stacks[src])):
            pos[stacks[src][k]] = (src, k)
    
    out = []
    for v, i in operations:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

solve()
