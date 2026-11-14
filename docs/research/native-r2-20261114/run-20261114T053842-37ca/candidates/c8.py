import sys
import random

def solve():
    input_data = sys.stdin.buffer.read().split()
    n, m = int(input_data[0]), int(input_data[1])
    k = n // m
    
    # stacks[i] is a list of box numbers from bottom to top
    stacks = []
    idx = 2
    for i in range(m):
        stack = [int(input_data[idx + j]) for j in range(k)]
        stacks.append(stack)
        idx += k
    
    def calculate_energy(stacks):
        """Calculate total energy needed to remove all boxes."""
        # We need to simulate the process of removing boxes 1 to n.
        # For each box v, we find its current stack and position.
        # If it's not at the top, we must move the boxes above it to another stack.
        # To minimize energy, we should move them to the stack that minimizes future costs.
        # However, a simple greedy strategy is to move them to the shortest stack (or an empty one).
        # Actually, the problem asks us to output the operations. The score depends on the sum of k+1 for each move.
        # Let's simulate the optimal sequence given the initial configuration.
        
        # A better approach: The cost is determined by how many times we have to 'unstack' things.
        # Let's just simulate the standard greedy removal:
        # For v from 1 to n:
        #   Find stack s containing v.
        #   If v is at top of s, remove it (cost 0).
        #   Else, let pos be index of v in s. Boxes above are s[pos+1:].
        #   We must move s[pos+1:] to some other stack t.
        #   Cost = len(s[pos+1:]) + 1.
        #   Which t to choose? It affects future costs. 
        #   Heuristic: Move to the stack with minimum length (excluding s) or where the moved boxes fit 'well'.
        #   Actually, since we just want to evaluate a configuration, we can use a fixed heuristic:
        #   Move to the stack with the smallest size (to keep stacks balanced/small).
        
        energy = 0
        # Copy stacks for simulation
        sim_stacks = [list(s) for s in stacks]
        
        for v in range(1, n + 1):
            found = False
            for i in range(m):
                if v in sim_stacks[i]:
                    pos = sim_stacks[i].index(v)
                    if pos == len(sim_stacks[i]) - 1:
                        # Top of stack, remove directly
                        sim_stacks[i].pop()
                    else:
                        # Need to move boxes above
                        above = sim_stacks[i][pos+1:]
                        num_above = len(above)
                        energy += num_above + 1
                        
                        # Choose destination stack
                        # Prefer empty stacks, then shortest
                        dest_idx = -1
                        min_len = float('inf')
                        for j in range(m):
                            if j != i:
                                l = len(sim_stacks[j])
                                if l < min_len:
                                    min_len = l
                                    dest_idx = j
                        
                        sim_stacks[dest_idx].extend(above)
                        del sim_stacks[i][pos+1:]
                    found = True
                    break
            if not found:
                return float('inf') # Should not happen
        return energy

    # Initial energy
    current_energy = calculate_energy(stacks)
    best_energy = current_energy
    best_stacks = [list(s) for s in stacks]
    
    # Simulated Annealing / Local Search
    # We will try swapping two boxes in different stacks, or moving a box within a stack?
    # Since the stacks are fixed in size initially, but operations change sizes.
    # Wait, the INPUT defines the initial stacks. We cannot change the initial assignment of boxes to stacks arbitrarily.
    # The problem says: "There are n cardboard boxes... divided into m stacks... b_{i,j} represents..."
    # So the initial state is FIXED. We cannot rearrange the initial stacks.
    # We can ONLY choose the SEQUENCE of operations.
    
    # Re-reading the problem:
    # "Please find a way to carry the boxes out that expends as little energy as possible."
    # The initial configuration is given. We must output the operations.
    # The c0 solution uses a greedy approach: always move the blocked boxes to the shortest other stack.
    # Is there a better choice for the destination stack?
    # Yes! The choice of destination stack affects future moves.
    
    # So the search space is the sequence of choices (which stack to move to) at each step.
    # This is a sequential decision problem. We can use Beam Search or Greedy with Lookahead.
    # Given n=200, depth is up to 200 steps. Branching factor is m-1 <= 9.
    # Beam Search with width W might work.
    
    # Let's implement Beam Search.
    
    def beam_search(stacks_initial, beam_width=50):
        # State: tuple of tuples representing stacks (immutable for hashing/copying)
        # Actually, lists are easier. We'll store a list of lists.
        # To make it hashable for deduplication (optional), we can convert to tuple of tuples.
        
        # State: (energy_so_far, stacks_tuple)
        # Start state
        init_stacks = tuple(tuple(s) for s in stacks_initial)
        beam = [(0, init_stacks)]
        
        next_val = 1
        
        for v in range(1, n + 1):
            new_beam = []
            for energy, stacks_t in beam:
                stacks_list = [list(s) for s in stacks_t]
                
                # Find where v is
                src_idx = -1
                pos = -1
                for i in range(m):
                    if v in stacks_list[i]:
                        src_idx = i
                        pos = stacks_list[i].index(v)
                        break
                
                if pos == len(stacks_list[src_idx]) - 1:
                    # Remove directly
                    stacks_list[src_idx].pop()
                    new_state = tuple(tuple(s) for s in stacks_list)
                    new_beam.append((energy, new_state))
                else:
                    above = stacks_list[src_idx][pos+1:]
                    num_above = len(above)
                    cost = num_above + 1
                    
                    # Try all possible destination stacks
                    for dest_idx in range(m):
                        if dest_idx == src_idx:
                            continue
                        
                        # Check if this move is valid? Yes, always valid.
                        new_stacks = [list(s) for s in stacks_list]
                        new_stacks[dest_idx].extend(above)
                        del new_stacks[src_idx][pos+1:]
                        
                        new_energy = energy + cost
                        new_state = tuple(tuple(s) for s in new_stacks)
                        new_beam.append((new_energy, new_state))
            
            # Keep only the best `beam_width` states
            # Sort by energy
            new_beam.sort(key=lambda x: x[0])
            beam = new_beam[:beam_width]
            
            # Optional: Deduplicate states to save memory/time
            # seen = set()
            # unique_beam = []
            # for e, s in beam:
            #     if s not in seen:
            #         seen.add(s)
            #         unique_beam.append((e, s))
            # beam = unique_beam
            
        # Return the best energy
        if not beam:
            return float('inf')
        return beam[0][0]

    # Run Beam Search
    # Beam width 50 might be slow if we do full simulation for each state.
    # But n=200, m=10. Depth 200. Branching ~9.
    # With beam width 50, we keep 50 states per layer.
    # Total states processed ~ 200 * 50 = 10000.
    # Each state transition involves copying lists of size ~20. Very fast.
    
    final_energy = beam_search(stacks, beam_width=100)
    
    print(f"Beam Search Energy: {final_energy}")
    
    # Now we need to RECONSTRUCT the path to output the operations.
    # We need to store parent pointers or re-run the search storing decisions.
    
    def beam_search_with_path(stacks_initial, beam_width=100):
        init_stacks = tuple(tuple(s) for s in stacks_initial)
        # State: (energy, stacks_t, path)
        # Path is a list of (v, operation_type, details)
        # Actually, we just need to store the decision made at each step for the best path.
        # Since we prune, we need to store the history for each state in the beam.
        # This increases memory. Path length is up to 200. 
        # 100 states * 200 steps * small data = fine.
        
        beam = [(0, init_stacks, [])]
        
        for v in range(1, n + 1):
            new_beam = []
            for energy, stacks_t, path in beam:
                stacks_list = [list(s) for s in stacks_t]
                
                src_idx = -1
                pos = -1
                for i in range(m):
                    if v in stacks_list[i]:
                        src_idx = i
                        pos = stacks_list[i].index(v)
                        break
                
                if pos == len(stacks_list[src_idx]) - 1:
                    stacks_list[src_idx].pop()
                    new_state = tuple(tuple(s) for s in stacks_list)
                    new_path = path + [(v, 0)] # Carry out
                    new_beam.append((energy, new_state, new_path))
                else:
                    above = stacks_list[src_idx][pos+1:]
                    num_above = len(above)
                    cost = num_above + 1
                    
                    for dest_idx in range(m):
                        if dest_idx == src_idx:
                            continue
                        
                        new_stacks = [list(s) for s in stacks_list]
                        new_stacks[dest_idx].extend(above)
                        del new_stacks[src_idx][pos+1:]
                        
                        new_energy = energy + cost
                        new_state = tuple(tuple(s) for s in new_stacks)
                        # Operation 1: Move box 'above[0]' (the one immediately above v) to dest_idx+1
                        # Wait, the operation is defined by (v_k, i_k).
                        # If we move the segment starting at `above[0]`, the box identifier is `above[0]`.
                        # And destination is `dest_idx + 1`.
                        new_path = path + [(above[0], dest_idx + 1)]
                        new_beam.append((new_energy, new_state, new_path))
            
            new_beam.sort(key=lambda x: x[0])
            beam = new_beam[:beam_width]
            
        if not beam:
            return None
        return beam[0][2]

    path = beam_search_with_path(stacks, beam_width=100)
    
    if path:
        for op in path:
            print(op[0], op[1])
    else:
        # Fallback to greedy if something went wrong
        pass

solve()
