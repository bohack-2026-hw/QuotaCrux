import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    idx = 2
    stacks = []
    for i in range(m):
        stack = data[idx:idx + n // m]
        stacks.append(stack)
        idx += n // m
    
    # Track positions of each box
    pos = {}  # pos[v] = (stack_index, position_in_stack)
    for i, stack in enumerate(stacks):
        for j, v in enumerate(stack):
            pos[v] = (i, j)
    
    operations = []
    total_energy = 0
    
    for value in range(1, n + 1):
        src_i, src_pos = pos[value]
        if src_pos < len(stacks[src_i]) - 1:
            # Need to move boxes above value
            above_boxes = stacks[src_i][src_pos + 1:]
            # Choose best destination stack
            # Heuristic: prefer stack where the topmost box in 'above' is largest
            # (so it won't block us for long), or shortest stack
            best_dest = None
            best_score = float('inf')
            for dest_i in range(m):
                if dest_i == src_i:
                    continue
                # Score: prioritize shorter stacks, and stacks where the moved boxes
                # have larger numbers on top (less likely to be needed soon)
                score = len(stacks[dest_i]) * 100
                # Add penalty based on how soon we might need these boxes
                for b in reversed(above_boxes):  # top first
                    if b > value:
                        score += max(0, b - value) * 10
                    break
                if score < best_score:
                    best_score = score
                    best_dest = dest_i
            
            if best_dest is not None:
                k = len(above_boxes)
                energy = k + 1
                total_energy += energy
                operations.append((above_boxes[0], best_dest + 1))
                
                # Update state
                stacks[best_dest].extend(above_boxes)
                del stacks[src_i][src_pos + 1:]
                for j, b in enumerate(above_boxes):
                    pos[b] = (best_dest, len(stacks[best_dest]) - len(above_boxes) + j)
                pos[value] = (src_i, src_pos)
        
        # Carry out value
        operations.append((value, 0))
        stacks[src_i].pop()
        del pos[value]
        # Update positions in source stack
        for j in range(len(stacks[src_i])):
            pos[stacks[src_i][j]] = (src_i, j)
    
    # Output
    out_lines = [f"{v} {i}" for v, i in operations]
    sys.stdout.write("\n".join(out_lines) + "\n")

solve()