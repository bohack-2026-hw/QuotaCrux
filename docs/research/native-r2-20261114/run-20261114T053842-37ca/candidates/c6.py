import sys

def solve():
    data = sys.stdin.buffer.read().split()
    it = iter(data)
    n = int(next(it))
    m = int(next(it))
    
    # Read stacks
    stacks = []
    for _ in range(m):
        stack = [int(next(it)) for _ in range(n // m)]
        stacks.append(stack)
    
    # Track position of each box
    pos = {}  # box_number -> (stack_index, position_in_stack)
    for i, stack in enumerate(stacks):
        for j, box in enumerate(stack):
            pos[box] = (i, j)
    
    operations = []
    
    def get_top(stack_idx):
        """Get the top box of a stack, or None if empty."""
        if stacks[stack_idx]:
            return stacks[stack_idx][-1]
        return None
    
    def find_min_remaining():
        """Find the minimum number among all remaining boxes."""
        min_box = float('inf')
        for i in range(m):
            for box in stacks[i]:
                if box < min_box:
                    min_box = box
        return min_box
    
    # Process boxes in ascending order
    for value in range(1, n + 1):
        src_i, src_j = pos[value]
        
        # Check if we need to move boxes above value
        if src_j + 1 < len(stacks[src_i]):
            # Find best destination: prefer empty stacks, then shortest
            best_dest = -1
            best_score = float('inf')
            
            for j in range(m):
                if j == src_i:
                    continue
                
                # Score: prefer empty stacks, then shorter stacks
                score = len(stacks[j])
                
                # Bonus for having smaller boxes on top (they might be needed soon)
                if stacks[j]:
                    top_box = stacks[j][-1]
                    # If top box is larger than current value, it's less urgent
                    if top_box > value:
                        score -= 1  # Slight preference for stacks with larger tops
                else:
                    score -= 2  # Strong preference for empty stacks
                
                if score < best_score:
                    best_score = score
                    best_dest = j
            
            # Move boxes above value to best destination
            above_boxes = stacks[src_i][src_j + 1:]
            first_above = above_boxes[0]
            operations.append((first_above, best_dest + 1))
            
            # Update state
            stacks[best_dest].extend(above_boxes)
            del stacks[src_i][src_j + 1:]
            
            # Update positions
            for k, box in enumerate(above_boxes):
                pos[box] = (best_dest, len(stacks[best_dest]) - len(above_boxes) + k)
        
        # Carry out the box
        operations.append((value, 0))
        
        # Remove from stack and update positions
        stacks[src_i].pop()
        new_len = len(stacks[src_i])
        for k in range(new_len):
            box = stacks[src_i][k]
            pos[box] = (src_i, k)
        del pos[value]
    
    # Output operations
    out_lines = []
    for v, i in operations:
        out_lines.append(f"{v} {i}")
    sys.stdout.write("\n".join(out_lines) + "\n")

solve()