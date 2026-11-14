import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]

# Create a position map for quick lookup
pos_map = {}
for i, stack in enumerate(stacks):
    for j, val in enumerate(stack):
        pos_map[val] = (i, j)

operations = []

def get_top_value(stack):
    """Get the top value of a stack, or infinity if empty."""
    if not stack:
        return float('inf')
    return stack[-1]

for value in range(1, n + 1):
    src, position = pos_map[value]
    
    # Remove boxes above 'value' from source stack and move them
    if position + 1 < len(stacks[src]):
        above = stacks[src][position + 1:]
        
        # Choose destination: prefer stack with smallest top value (not source)
        best_dest = -1
        best_top = float('inf')
        for j in range(m):
            if j == src:
                continue
            top_val = get_top_value(stacks[j])
            if top_val < best_top:
                best_top = top_val
                best_dest = j
        
        if best_dest == -1:
            # All other stacks are empty, pick any
            best_dest = (src + 1) % m
        
        operations.append((above[0], best_dest + 1))
        
        # Update position map for moved boxes
        for box in above:
            del pos_map[box]
        
        # Move boxes
        stacks[best_dest].extend(above)
        del stacks[src][position + 1:]
        
        # Update position map for destination stack
        base_idx = len(stacks[best_dest]) - len(above)
        for k, box in enumerate(above):
            pos_map[box] = (best_dest, base_idx + k)
    
    # Carry out the box
    operations.append((value, 0))
    del pos_map[value]
    stacks[src].pop()
    
    # Update positions for remaining boxes in source stack
    for k in range(position):
        pos_map[stacks[src][k]] = (src, k)

# Output operations
out_lines = [f"{v} {i}" for v, i in operations]
sys.stdout.write("\n".join(out_lines) + "\n")
