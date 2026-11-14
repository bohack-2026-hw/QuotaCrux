import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    idx = 0
    n, m = data[idx], data[idx+1]
    idx += 2
    h = n // m
    stacks = []
    for i in range(m):
        stacks.append(data[idx:idx+h])
        idx += h
    
    ops = []
    
    # Position map for fast lookup
    def build_pos(stacks):
        pos = {}
        for si, st in enumerate(stacks):
            for pi, v in enumerate(st):
                pos[v] = (si, pi)
        return pos
    
    pos = build_pos(stacks)
    
    def simulate_future_cost(stacks_state, next_values, steps=5):
        """Simulate the next 'steps' operations and count extra moves needed."""
        import copy
        state = [s[:] for s in stacks_state]
        cost = 0
        for val in next_values:
            if val > n or val not in {v for st in state for v in st}:
                continue
            # Find where val is
            found = False
            for si, st in enumerate(state):
                if val in st:
                    p = st.index(val)
                    if p + 1 < len(st):
                        # Need to move boxes above val
                        k = len(st) - p - 1
                        cost += k + 1
                    break
        return cost
    
    for value in range(1, n + 1):
        si, pi = pos[value]
        if pi + 1 < len(stacks[si]):
            above = stacks[si][pi+1:]
            max_above = max(above)
            min_above = min(above)
            
            # Find candidate destinations
            candidates = []
            for di in range(m):
                if di == si:
                    continue
                if len(stacks[di]) == 0:
                    # Empty stack is always valid
                    candidates.append((di, 'empty'))
                else:
                    min_in_dest = min(stacks[di])
                    if min_in_dest > max_above:
                        # Valid destination
                        candidates.append((di, 'valid'))
            
            if candidates:
                # Choose best among valid candidates using future cost simulation
                best_dest = -1
                best_score = float('inf')
                
                # Next few values to consider for simulation
                next_vals = [value + j for j in range(1, 6) if value + j <= n]
                
                for di, status in candidates:
                    # Simulate moving 'above' to di
                    sim_stacks = [s[:] for s in stacks]
                    sim_stacks[di].extend(above[:])
                    del sim_stacks[si][pi+1:]
                    
                    # Calculate future cost
                    fc = simulate_future_cost(sim_stacks, next_vals)
                    
                    # Also factor in current stack length preference
                    dest_len = len(stacks[di])
                    score = fc * 10 + dest_len
                    
                    if score < best_score:
                        best_score = score
                        best_dest = di
                
                if best_dest == -1:
                    best_dest = candidates[0][0]
            else:
                # No valid candidate; choose the one with minimum violation
                # Violation = how many boxes in dest have number <= max_above
                best_dest = -1
                best_violation = float('inf')
                for di in range(m):
                    if di == si:
                        continue
                    if len(stacks[di]) == 0:
                        violation = 0
                    else:
                        violation = sum(1 for x in stacks[di] if x <= max_above)
                    if violation < best_violation:
                        best_violation = violation
                        best_dest = di
                
                if best_dest == -1:
                    best_dest = min((j for j in range(m) if j != si), key=lambda j: len(stacks[j]))
            
            ops.append((above[0], best_dest + 1))
            stacks[best_dest].extend(above)
            del stacks[si][pi+1:]
            pos = build_pos(stacks)
        
        ops.append((value, 0))
        stacks[si].pop()
        pos = build_pos(stacks)
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

solve()