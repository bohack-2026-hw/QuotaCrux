import sys
from collections import defaultdict

def solve():
    data = sys.stdin.buffer.read().split()
    it = iter(data)
    n = int(next(it))
    m = int(next(it))
    
    # Read stacks
    stacks = []
    for i in range(m):
        stack = [int(next(it)) for _ in range(n // m)]
        stacks.append(stack)
    
    # Position map: box -> (stack_idx, pos_in_stack)
    pos_map = {}
    for i, stack in enumerate(stacks):
        for j, box in enumerate(stack):
            pos_map[box] = (i, j)
    
    operations = []
    total_energy = 0
    
    for v in range(1, n + 1):
        src, pos = pos_map[v]
        
        if pos < len(stacks[src]) - 1:
            # Need to move boxes above v
            above = stacks[src][pos + 1:]
            
            # Find best destination
            # Strategy: move to the stack that will help us most
            # Prefer moving to a stack where the top box is the smallest among remaining
            best_dest = None
            best_score = float('inf')
            
            for dest in range(m):
                if dest == src:
                    continue
                
                # Score based on how well this helps
                # If dest stack is empty or has small numbers on top, it's good
                if not stacks[dest]:
                    score = 0
                else:
                    # Look at what's on top of dest
                    top_box = stacks[dest][-1]
                    # We want to minimize future moves
                    # A good heuristic: prefer destinations where the combined
                    # stack will have better ordering
                    score = len(stacks[dest])
                
                if score < best_score:
                    best_score = score
                    best_dest = dest
            
            # Move 'above' boxes to best_dest
            k = len(above)
            energy = k + 1
            total_energy += energy
            operations.append((above[0], best_dest + 1))
            
            # Update stacks
            moved = stacks[src][pos + 1:]
            del stacks[src][pos + 1:]
            stacks[best_dest].extend(moved)
            
            # Update pos_map for moved boxes
            for idx, box in enumerate(moved):
                pos_map[box] = (best_dest, len(stacks[best_dest]) - len(moved) + idx)
        
        # Carry out box v
        operations.append((v, 0))
        
        # Remove v from its stack
        del stacks[src][pos]
        # Update pos_map for boxes below v in src
        for j in range(pos, len(stacks[src])):
            pos_map[stacks[src][j]] = (src, j)
    
    # Output
    out = []
    for v, i in operations:
        out.append(f"{v} {i}")
    print('\n'.join(out))

solve()
