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
    
    def simulate(stacks_state, next_val, L, greedy_mode='shortest'):
        """Simulate L steps from current state, return total energy cost."""
        cost = 0
        carried = set(carried_out)
        # Copy stacks
        ss = [list(s) for s in stacks_state]
        
        for step in range(L):
            v = next_val + step
            if v > n:
                break
            # Find v's stack and position
            src = None
            pos = None
            for i, stack in enumerate(ss):
                if v in stack:
                    src = i
                    pos = stack.index(v)
                    break
            if src is None:
                continue
            
            if pos + 1 < len(ss[src]):
                # Need to move block above v
                k = len(ss[src]) - pos - 1
                cost += k + 1
                # Choose destination based on greedy mode
                if greedy_mode == 'shortest':
                    dest = min((j for j in range(m) if j != src), key=lambda j: len(ss[j]))
                else:
                    # Choose stack with largest min remaining box
                    best_dest = -1
                    best_score = None
                    for j in range(m):
                        if j == src:
                            continue
                        min_rem = None
                        for box in ss[j]:
                            if box not in carried:
                                if min_rem is None or box < min_rem:
                                    min_rem = box
                        if min_rem is None:
                            score = (float('inf'), -len(ss[j]))
                        else:
                            score = (min_rem, -len(ss[j]))
                        if best_score is None or score > best_score:
                            best_score = score
                            best_dest = j
                    dest = best_dest
                
                above = ss[src][pos+1:]
                ss[dest].extend(above)
                del ss[src][pos+1:]
            
            # Carry out v
            carried.add(v)
            ss[src].pop()
        
        return cost
    
    for value in range(1, n + 1):
        src = None
        pos = None
        for i, stack in enumerate(stacks):
            if value in stack:
                src = i
                pos = stack.index(value)
                break
        
        if pos + 1 < len(stacks[src]):
            # Need to move block above value
            k = len(stacks[src]) - pos - 1
            
            # Lookahead: try each destination and simulate future
            best_dest = -1
            best_cost = float('inf')
            L = 12  # lookahead depth
            
            for t in range(m):
                if t == src:
                    continue
                # Simulate: move block to t, then carry out value, then L more steps
                sim_stacks = [list(s) for s in stacks]
                above = sim_stacks[src][pos+1:]
                sim_stacks[t].extend(above)
                del sim_stacks[src][pos+1:]
                # Carry out value
                sim_stacks[src].pop()
                
                # Now simulate L more steps starting from value+1
                future_cost = simulate(sim_stacks, value, L, 'shortest')
                total_cost = k + 1 + future_cost
                
                if total_cost < best_cost:
                    best_cost = total_cost
                    best_dest = t
            
            above = stacks[src][pos+1:]
            ops.append((above[0], best_dest + 1))
            stacks[best_dest].extend(above)
            del stacks[src][pos+1:]
        
        ops.append((value, 0))
        carried_out.add(value)
        stacks[src].pop()
    
    for v, i in ops:
        print(v, i)

solve()