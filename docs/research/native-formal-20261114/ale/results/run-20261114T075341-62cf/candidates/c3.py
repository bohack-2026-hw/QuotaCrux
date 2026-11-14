import sys

def solve():
    it = iter(map(int, sys.stdin.buffer.read().split()))
    n, m = next(it), next(it)
    h = n // m
    stacks = [[next(it) for _ in range(h)] for _ in range(m)]
    
    # Build position map: box_value -> (stack_index, position_in_stack)
    pos = {}
    for i, stack in enumerate(stacks):
        for j, v in enumerate(stack):
            pos[v] = (i, j)
    
    operations = []
    energy = 0
    
    for value in range(1, n + 1):
        src, position = pos[value]
        if position < len(stacks[src]) - 1:
            # Need to move boxes above value
            above_count = len(stacks[src]) - position - 1
            # Choose destination stack that minimizes future cost
            # Heuristic: choose the shortest stack (not source)
            best_dest = min((j for j in range(m) if j != src), key=lambda j: len(stacks[j]))
            
            # Move the top 'above_count' boxes from src to best_dest
            moved_boxes = stacks[src][position + 1:]
            dest_idx = best_dest
            
            # Record operation: move box at position+1 (top of remaining after value) to dest_idx
            # The box we're moving is stacks[src][position+1]
            top_box = moved_boxes[0]
            operations.append((top_box, dest_idx + 1))
            energy += above_count + 1
            
            # Update stacks
            stacks[dest_idx].extend(moved_boxes)
            del stacks[src][position + 1:]
            
            # Update positions for moved boxes
            for k, box in enumerate(moved_boxes):
                pos[box] = (dest_idx, len(stacks[dest_idx]) - above_count + k)
        
        # Carry out value
        operations.append((value, 0))
        stacks[src].pop()
        del pos[value]
        
        # Update positions in src stack (boxes below shift down? No, they stay same index)
        # Actually positions don't change for remaining boxes in src
    
    print(len(operations))
    for v, i in operations:
        print(v, i)

solve()