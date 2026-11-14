import sys

def solve():
    it = iter(map(int, sys.stdin.buffer.read().split()))
    n, m = next(it), next(it)
    stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
    
    # Build position map: box -> (stack_index, position_in_stack)
    pos_map = {}
    for i, stack in enumerate(stacks):
        for j, box in enumerate(stack):
            pos_map[box] = (i, j)
    
    operations = []
    
    def move_boxes(src, pos, dest):
        """Move boxes from src[pos:] to top of dest. Returns number moved."""
        boxes_to_move = stacks[src][pos:]
        k = len(boxes_to_move)
        if k == 0:
            return 0
        # Update pos_map for moved boxes
        for idx, box in enumerate(boxes_to_move):
            pos_map[box] = (dest, len(stacks[dest]) + idx)
        # Remove from src
        del stacks[src][pos:]
        # Add to dest
        stacks[dest].extend(boxes_to_move)
        # Record operation: we're moving the bottom-most box of the group
        operations.append((boxes_to_move[0], dest + 1))
        return k
    
    def carry_out(box):
        """Carry out box from top of its stack."""
        src, pos = pos_map[box]
        assert pos == len(stacks[src]) - 1, f"Box {box} not at top of stack {src}"
        del stacks[src][pos]
        # Update pos_map for remaining boxes in this stack (positions shift down by 1)
        for idx in range(pos):
            b = stacks[src][idx]
            pos_map[b] = (src, idx)
        del pos_map[box]
        operations.append((box, 0))
    
    for value in range(1, n + 1):
        src, pos = pos_map[value]
        above = stacks[src][pos + 1:]
        
        if not above:
            carry_out(value)
            continue
        
        # Choose best destination stack
        best_dest = -1
        best_cost = float('inf')
        
        for dest in range(m):
            if dest == src:
                continue
            # Cost: after placing 'above' on top of dest,
            # how many inversions exist within 'above' relative to existing dest stack?
            # Simpler cost: count pairs (a,b) in above where a < b but a is above b
            # This means when we later try to take out a, b will be blocking it.
            
            # Actually, the key insight: after moving 'above' to dest's top,
            # the total cost contributed by these boxes depends on their internal ordering.
            # If above is already in increasing order (bottom to top), then we can take them out
            # one by one without any additional moves.
            # The cost is related to the number of "blocking" relationships.
            
            # Let's use a simpler heuristic: prefer dest stacks that are shorter,
            # and among those, prefer ones where the top element is larger than min(above).
            
            # Better heuristic: compute the number of inversions in 'above'
            # (pairs where smaller number is above larger number)
            inv_count = 0
            for i2 in range(len(above)):
                for j2 in range(i2 + 1, len(above)):
                    if above[i2] > above[j2]:
                        inv_count += 1
            
            # Also consider interaction with existing dest stack content
            # Boxes in 'above' that are smaller than some boxes in dest stack
            # will need to be moved again when trying to take them out.
            interaction = 0
            for a in above:
                for d in stacks[dest]:
                    if a < d:
                        interaction += 1
            
            cost = inv_count * 2 + interaction + len(stacks[dest]) * 0.1
            
            if cost < best_cost:
                best_cost = cost
                best_dest = dest
        
        move_boxes(src, pos + 1, best_dest)
        carry_out(value)
    
    print('\n'.join(f'{v} {i}' for v, i in operations))

solve()
