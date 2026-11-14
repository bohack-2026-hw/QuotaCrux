import sys

def solve():
    data = sys.stdin.buffer.read().split()
    it = iter(data)
    n = int(next(it))
    m = int(next(it))
    h = n // m
    stacks = []
    for i in range(m):
        stack = [int(next(it)) for _ in range(h)]
        stacks.append(stack)
    
    # Position of each box: (stack_index, position_in_stack)
    pos = {}
    for i, stack in enumerate(stacks):
        for j, box in enumerate(stack):
            pos[box] = (i, j)
    
    operations = []
    energy = 0
    
    for value in range(1, n + 1):
        src, pos_in_src = pos[value]
        
        if pos_in_src < len(stacks[src]) - 1:
            # Need to move boxes above value
            above_boxes = stacks[src][pos_in_src + 1:]
            k = len(above_boxes)
            
            # Choose destination stack
            # Strategy: pick the stack that minimizes future disruption
            # Prefer shorter stacks, but also consider which boxes are above
            best_dest = None
            best_score = float('inf')
            for dest in range(m):
                if dest == src:
                    continue
                # Score: length of dest stack (shorter is better)
                score = len(stacks[dest])
                # Penalize if dest stack has boxes that need to be moved soon
                for box in stacks[dest]:
                    if box > value and box < value + k * 2:
                        score += 1
                if score < best_score:
                    best_score = score
                    best_dest = dest
            
            if best_dest is None:
                best_dest = (src + 1) % m
            
            operations.append((above_boxes[0], best_dest + 1))
            energy += k + 1
            
            # Update positions
            for box in above_boxes:
                del pos[box]
            stacks[best_dest].extend(above_boxes)
            for j, box in enumerate(above_boxes):
                pos[box] = (best_dest, len(stacks[best_dest]) - k + j)
            
            # Remove from source
            del stacks[src][pos_in_src + 1:]
        
        # Carry out value
        operations.append((value, 0))
        del pos[value]
        stacks[src].pop()
    
    out = []
    for v, i in operations:
        out.append(f"{v} {i}")
    print("\n".join(out))

solve()
