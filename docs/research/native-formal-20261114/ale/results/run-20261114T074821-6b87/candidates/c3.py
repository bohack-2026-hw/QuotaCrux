import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    h = n // m
    stacks = []
    idx = 2
    for i in range(m):
        stacks.append(data[idx:idx+h])
        idx += h
    
    ops = []
    carried_out = set()
    
    for value in range(1, n + 1):
        # Find value's stack and position
        src = None
        pos = None
        for i, stack in enumerate(stacks):
            if value in stack:
                src = i
                pos = stack.index(value)
                break
        
        if pos + 1 < len(stacks[src]):
            # Need to move block above value
            above = stacks[src][pos+1:]
            b_min = min(above)  # Minimum value in the block
            
            # Score each candidate destination
            best_dest = -1
            best_score = None
            
            for t in range(m):
                if t == src:
                    continue
                
                # Get remaining boxes in stack t
                remaining = [box for box in stacks[t] if box not in carried_out]
                
                if not remaining:
                    # Empty stack - best target
                    score = (2, 0, float('inf'), -len(stacks[t]))
                else:
                    min_rem = min(remaining)
                    max_rem = max(remaining)
                    
                    # Check compatibility: all remaining boxes > b_min
                    is_compatible = all(box > b_min for box in remaining)
                    
                    if is_compatible:
                        # Compatible stack - good target
                        score = (1, 0, min_rem, -len(stacks[t]))
                    else:
                        # Not compatible - less ideal
                        score = (0, 0, min_rem, -len(stacks[t]))
                
                if best_score is None or score > best_score:
                    best_score = score
                    best_dest = t
            
            # Execute the move
            ops.append((above[0], best_dest + 1))
            stacks[best_dest].extend(above)
            del stacks[src][pos+1:]
        
        # Carry out value
        ops.append((value, 0))
        carried_out.add(value)
        stacks[src].pop()
    
    for v, i in ops:
        print(v, i)

solve()