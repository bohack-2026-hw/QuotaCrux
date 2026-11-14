import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]

# Precompute position of each box
pos = {}
for i, stack in enumerate(stacks):
    for j, val in enumerate(stack):
        pos[val] = (i, j)

operations = []

def find_stack_with_box(value):
    """Find which stack contains the given value and its position"""
    for i, stack in enumerate(stacks):
        if value in stack:
            return i, stack.index(value)
    return None, None

def score_destination(dest_idx, src_idx, boxes_to_move, next_values):
    """Score a destination stack based on future needs"""
    # Penalize if destination contains boxes we'll need soon
    penalty = 0
    dest_set = set(stacks[dest_idx])
    for v in next_values:
        if v in dest_set:
            penalty += 1
    
    # Prefer shorter stacks
    length_bonus = -len(stacks[dest_idx]) * 0.1
    
    return penalty + length_bonus

for value in range(1, n + 1):
    src, position = find_stack_with_box(value)
    
    if position is not None and position + 1 < len(stacks[src]):
        above = stacks[src][position + 1:]
        
        # Look ahead to see which boxes we'll need next
        next_values = list(range(value + 1, min(value + 20, n + 1)))
        
        # Score all possible destinations
        best_dest = None
        best_score = float('inf')
        
        for dest in range(m):
            if dest == src:
                continue
            score = score_destination(dest, src, above, next_values)
            if score < best_score:
                best_score = score
                best_dest = dest
        
        operations.append((above[0], best_dest + 1))
        stacks[best_dest].extend(above)
        del stacks[src][position + 1:]
    
    operations.append((value, 0))
    stacks[src].pop()

# Output operations
out_lines = [f"{v} {i}" for v, i in operations]
sys.stdout.write('\n'.join(out_lines) + '\n')
