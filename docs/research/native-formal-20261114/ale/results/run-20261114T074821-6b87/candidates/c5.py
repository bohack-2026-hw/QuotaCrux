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
    
    # Position tracking: pos[v] = (stack_idx, position_in_stack)
    pos = {}
    for i, stack in enumerate(stacks):
        for j, v in enumerate(stack):
            pos[v] = (i, j)
    
    ops = []
    carried_out = set()
    L = 20  # lookahead depth
    
    def simulate_future(stacks_state, next_val, depth):
        """Simulate 'depth' more steps using shortest-stack greedy, return total energy cost."""
        ss = [list(s) for s in stacks_state]
        # Build pos for simulation
        spos = {}
        for i, stack in enumerate(ss):
            for j, v in enumerate(stack):
                if v not in carried_out:
                    spos[v] = (i, j)
        
        cost = 0
        sim_carried = set(carried_out)
        
        for step in range(depth):
            v = next_val + step
            if v > n:
                break
            if v in sim_carried:
                continue
            if v not in spos:
                continue
            src, p = spos[v]
            
            if p + 1 < len(ss[src]):
                # Need to move block above v
                k = len(ss[src]) - p - 1
                cost += k + 1
                # Choose shortest destination
                dest = min((j for j in range(m) if j != src), key=lambda j: len(ss[j]))
                above = ss[src][p+1:]
                # Update positions for moved boxes
                for box in above:
                    del spos[box]
                ss[dest].extend(above)
                del ss[src][p+1:]
                for k2, box in enumerate(above):
                    spos[box] = (dest, len(ss[dest]) - len(above) + k2)
            
            # Carry out v
            sim_carried.add(v)
            del spos[v]
            ss[src].pop()
            # Update positions of boxes below v in src
            for j in range(p):
                spos[ss[src][j]] = (src, j)
        
        return cost
    
    for value in range(1, n + 1):
        src, p = pos[value]
        
        if p + 1 < len(stacks[src]):
            # Need to move block above value
            above = stacks[src][p+1:]
            k = len(above)
            
            # Evaluate each candidate destination
            best_dest = -1
            best_cost = float('inf')
            
            for t in range(m):
                if t == src:
                    continue
                
                # Simulate: move block to t, carry out value, then L more steps
                sim_stacks = [list(s) for s in stacks]
                sim_stacks[t].extend(list(above))
                del sim_stacks[src][p+1:]
                # Carry out value
                sim_stacks[src].pop()
                
                future_cost = simulate_future(sim_stacks, value + 1, L)
                total_cost = k + 1 + future_cost
                
                if total_cost < best_cost:
                    best_cost = total_cost
                    best_dest = t
            
            # Execute the move
            ops.append((above[0], best_dest + 1))
            # Update positions for moved boxes
            for box in above:
                del pos[box]
            stacks[best_dest].extend(above)
            del stacks[src][p+1:]
            for k2, box in enumerate(above):
                pos[box] = (best_dest, len(stacks[best_dest]) - len(above) + k2)
        
        # Carry out value
        ops.append((value, 0))
        carried_out.add(value)
        del pos[value]
        stacks[src].pop()
        # Update positions of boxes below value in src
        for j in range(p):
            pos[stacks[src][j]] = (src, j)
    
    for v, i in ops:
        print(v, i)

solve()