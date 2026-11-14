import sys

def main():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    h = n // m
    stacks = []
    idx = 2
    for i in range(m):
        stacks.append(data[idx:idx+h])
        idx += h
    
    ops = []
    
    # For each stack, maintain the set of boxes in it for quick lookup
    # We'll use a simpler approach: just track positions
    pos_stack = [0] * (n + 1)  # which stack box v is in
    pos_idx = [0] * (n + 1)    # position within that stack
    
    def update_positions():
        for i in range(m):
            for j, v in enumerate(stacks[i]):
                pos_stack[v] = i
                pos_idx[v] = j
    
    update_positions()
    
    for value in range(1, n + 1):
        src = pos_stack[value]
        p = pos_idx[value]
        if p < len(stacks[src]) - 1:
            above_count = len(stacks[src]) - 1 - p
            # Choose destination to minimize future cost
            # Heuristic: move to stack where the topmost box has largest number
            # (so those boxes won't need to be moved again soon)
            best_dest = None
            best_score = float('inf')
            for j in range(m):
                if j == src:
                    continue
                # Score: prefer shorter stacks, and stacks whose top box is large
                score = len(stacks[j])
                if stacks[j]:
                    score -= stacks[j][-1] / 1000.0  # slight preference for larger top
                else:
                    score -= 0.5  # prefer empty stacks
                if score < best_score:
                    best_score = score
                    best_dest = j
            
            ops.append((stacks[src][p+1], best_dest + 1))
            # Move boxes
            moved = stacks[src][p+1:]
            del stacks[src][p+1:]
            stacks[best_dest].extend(moved)
            update_positions()
        
        ops.append((value, 0))
        # Remove value from its stack
        si = pos_stack[value]
        pi = pos_idx[value]
        del stacks[si][pi]
        update_positions()
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

main()