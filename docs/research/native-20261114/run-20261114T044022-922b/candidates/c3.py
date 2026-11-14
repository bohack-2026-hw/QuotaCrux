import sys

def solve():
    input = sys.stdin.read().split()
    if not input:
        return
    it = iter(input)
    n = int(next(it))
    m = int(next(it))
    k = n // m
    stacks = []
    for _ in range(m):
        stack = [int(next(it)) for _ in range(k)]
        stacks.append(stack)
    
    # Position of each box: (stack_index, position_in_stack)
    pos = {}
    for i in range(m):
        for j, val in enumerate(stacks[i]):
            pos[val] = (i, j)
    
    operations = []
    energy = 0
    
    for v in range(1, n + 1):
        si, sj = pos[v]
        # If v is not at the top, we need to move the boxes above it
        if sj < len(stacks[si]) - 1:
            # Boxes above v are from sj+1 to end of stacks[si]
            above_boxes = stacks[si][sj+1:]
            
            # Find destination stack
            # Heuristic: Move to a stack that minimizes future disruption.
            # A good heuristic is to move to an empty stack if available.
            # Otherwise, move to the stack with the largest minimum value among remaining boxes?
            # Or simply the shortest stack as before? Let's try moving to the stack with the most 'space' or least likely to block others.
            # Actually, a common strategy in these problems is to move the block to a stack where the bottom-most box is larger than v, or just pick an arbitrary different stack.
            # Let's stick to picking the shortest stack first, but maybe prefer empty ones.
            
            dest_idx = -1
            min_len = float('inf')
            for j in range(m):
                if j == si:
                    continue
                if len(stacks[j]) < min_len:
                    min_len = len(stacks[j])
                    dest_idx = j
            
            # Perform move
            # Operation 1: Move box above_boxes[0] (which is at pos si, sj+1) to dest_idx
            # The box being moved is the one directly on top of v, which is above_boxes[0]
            move_box_val = above_boxes[0]
            operations.append((move_box_val, dest_idx + 1))
            
            # Update state
            # Remove above_boxes from si
            del stacks[si][sj+1:]
            # Add to dest_idx
            stacks[dest_idx].extend(above_boxes)
            
            # Update positions for moved boxes
            base_pos = len(stacks[dest_idx]) - len(above_boxes)
            for idx, box_val in enumerate(above_boxes):
                pos[box_val] = (dest_idx, base_pos + idx)
            
            energy += len(above_boxes) + 1
        
        # Now v is at the top of si
        # Carry out v
        operations.append((v, 0))
        
        # Update state: remove v from si
        stacks[si].pop()
        # Update positions for boxes below v? No, their relative positions don't change, but absolute indices do if we pop from end.
        # Since we always pop from the end (top), and v was at the top, the indices of remaining boxes in si stay the same.
        # Wait, if v was at index sj, and we popped it, the list length decreases by 1.
        # The boxes below v (indices 0..sj-1) keep their indices.
        # So no position update needed for them.
        
    # Output
    print(len(operations)) # Wait, output format doesn't ask for K first? 
    # "Output the obtained sequence of operations ... to Standard Output in the following format: v1 i1 ..." 
    # It does NOT say to print K first. Just the lines.
    
    out_lines = []
    for v, i in operations:
        out_lines.append(f"{v} {i}")
    sys.stdout.write("\n".join(out_lines) + "\n")

solve()