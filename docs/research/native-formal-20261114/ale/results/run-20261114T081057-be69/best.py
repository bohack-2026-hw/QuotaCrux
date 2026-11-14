import sys

def simulate(stacks, m):
    """Simulate the process and return total energy."""
    # Make a copy of stacks
    import copy
    sim_stacks = [list(s) for s in stacks]
    
    # Position map: box value -> (stack_index, position_in_stack)
    pos_map = {}
    for i, stack in enumerate(sim_stacks):
        for j, val in enumerate(stack):
            pos_map[val] = (i, j)
    
    total_energy = 0
    
    for value in range(1, len(pos_map) + 1):
        if value not in pos_map:
            continue
        src_idx, src_pos = pos_map[value]
        
        # Check if there are boxes above
        if src_pos + 1 < len(sim_stacks[src_idx]):
            # Need to move boxes above
            above_boxes = sim_stacks[src_idx][src_pos + 1:]
            k = len(above_boxes)
            
            # Choose best destination by simulation
            best_dest = -1
            best_future_cost = float('inf')
            
            for dest_idx in range(m):
                if dest_idx == src_idx:
                    continue
                
                # Try moving to dest_idx
                # Create temporary state
                temp_stacks = [list(s) for s in sim_stacks]
                temp_above = temp_stacks[src_idx][src_pos + 1:]
                del temp_stacks[src_idx][src_pos + 1:]
                temp_stacks[dest_idx].extend(temp_above)
                
                # Update temp pos_map
                temp_pos_map = dict(pos_map)
                for val in temp_above:
                    del temp_pos_map[val]
                for j, val in enumerate(temp_stacks[dest_idx]):
                    temp_pos_map[val] = (dest_idx, j)
                # Also update positions in src stack after deletion
                for j, val in enumerate(temp_stacks[src_idx]):
                    temp_pos_map[val] = (src_idx, j)
                
                # Simulate future from here (limited lookahead)
                future_cost = 0
                remaining_values = [v for v in range(value + 1, len(pos_map) + 1) if v in temp_pos_map]
                
                # Quick estimate: count how many times each remaining box would need to be moved
                # For each remaining box, check if it has smaller boxes above it in its current stack
                for rem_val in remaining_values:
                    ri, rp = temp_pos_map[rem_val]
                    stack_above = temp_stacks[ri][rp + 1:]
                    # Count boxes above that are smaller than rem_val
                    smaller_above = sum(1 for b in stack_above if b < rem_val)
                    future_cost += smaller_above
                
                if future_cost < best_future_cost:
                    best_future_cost = future_cost
                    best_dest = dest_idx
            
            if best_dest == -1:
                # Fallback: choose shortest non-source stack
                best_dest = min((j for j in range(m) if j != src_idx), key=lambda j: len(sim_stacks[j]))
            
            # Execute the move
            above_boxes = sim_stacks[src_idx][src_pos + 1:]
            k = len(above_boxes)
            total_energy += k + 1
            
            # Update pos_map
            for val in above_boxes:
                del pos_map[val]
            del sim_stacks[src_idx][src_pos + 1:]
            sim_stacks[best_dest].extend(above_boxes)
            for j, val in enumerate(sim_stacks[best_dest]):
                pos_map[val] = (best_dest, j)
            for j, val in enumerate(sim_stacks[src_idx]):
                pos_map[val] = (src_idx, j)
        
        # Carry out the box
        del pos_map[value]
        sim_stacks[src_idx].pop()
        for j, val in enumerate(sim_stacks[src_idx]):
            pos_map[val] = (src_idx, j)
    
    return total_energy

# Main solution
data = list(map(int, sys.stdin.buffer.read().split()))
n, m = data[0], data[1]
idx = 2
stacks = []
for i in range(m):
    stack = data[idx:idx + n // m]
    idx += n // m
    stacks.append(stack)

# Build position map
pos_map = {}
for i, stack in enumerate(stacks):
    for j, val in enumerate(stack):
        pos_map[val] = (i, j)

operations = []
total_energy = 0

for value in range(1, n + 1):
    if value not in pos_map:
        continue
    src_idx, src_pos = pos_map[value]
    
    if src_pos + 1 < len(stacks[src_idx]):
        above_boxes = stacks[src_idx][src_pos + 1:]
        k = len(above_boxes)
        
        # Choose best destination using lookahead simulation
        best_dest = -1
        best_future_cost = float('inf')
        
        for dest_idx in range(m):
            if dest_idx == src_idx:
                continue
            
            # Estimate future cost if we move to dest_idx
            # After moving, check how many inversions are created
            new_top_of_dest = stacks[dest_idx][-1] if stacks[dest_idx] else None
            min_above = min(above_boxes)
            max_above = max(above_boxes)
            
            # Cost estimation: 
            # 1. If min_above > new_top_of_dest, then new_top_of_dest will need to be moved later
            # 2. Count internal inversions in above_boxes relative to dest stack
            
            future_cost = 0
            
            # Inversions within above_boxes: pairs where lower box has larger value
            for a_i in range(len(above_boxes)):
                for b_i in range(a_i + 1, len(above_boxes)):
                    if above_boxes[a_i] > above_boxes[b_i]:
                        future_cost += 1
            
            # Interaction with dest stack top
            if new_top_of_dest is not None:
                if min_above > new_top_of_dest:
                    # The dest top will be blocked by all above_boxes
                    future_cost += len(above_boxes)
                else:
                    # Some boxes in above_boxes are smaller than dest top
                    # Those will be taken before dest top, which is good
                    pass
            
            # Prefer shorter stacks
            future_cost += len(stacks[dest_idx]) * 0.1
            
            if future_cost < best_future_cost:
                best_future_cost = future_cost
                best_dest = dest_idx
        
        if best_dest == -1:
            best_dest = min((j for j in range(m) if j != src_idx), key=lambda j: len(stacks[j]))
        
        # Execute move
        operations.append((above_boxes[0], best_dest + 1))
        total_energy += k + 1
        
        # Update state
        for val in above_boxes:
            del pos_map[val]
        del stacks[src_idx][src_pos + 1:]
        stacks[best_dest].extend(above_boxes)
        for j, val in enumerate(stacks[best_dest]):
            pos_map[val] = (best_dest, j)
        for j, val in enumerate(stacks[src_idx]):
            pos_map[val] = (src_idx, j)
    
    # Carry out
    operations.append((value, 0))
    del pos_map[value]
    stacks[src_idx].pop()
    for j, val in enumerate(stacks[src_idx]):
        pos_map[val] = (src_idx, j)

# Output
out_lines = [f"{v} {i}" for v, i in operations]
sys.stdout.write("\n".join(out_lines) + "\n")
