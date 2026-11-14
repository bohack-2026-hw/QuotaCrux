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
    
    # Position map: box -> (stack_index, position_in_stack)
    pos = {}
    for si in range(m):
        for pi, box in enumerate(stacks[si]):
            pos[box] = (si, pi)
    
    ops = []
    energy = 0
    
    def find_box(box):
        """Return (stack_idx, pos_in_stack) or None if already removed."""
        return pos.get(box)
    
    def remove_top(si):
        """Remove top box from stack si, update pos map."""
        box = stacks[si].pop()
        del pos[box]
    
    def move_above(v, dest_si):
        """Move all boxes above v (inclusive) from its current stack to dest_si.
        Returns the number of boxes moved."""
        src_si, src_pi = pos[v]
        # Boxes to move: stacks[src_si][src_pi:]
        moving = stacks[src_si][src_pi:]
        k = len(moving)
        # Update positions
        for box in moving:
            del pos[box]
        # Remove from source
        del stacks[src_si][src_pi:]
        # Add to destination
        stacks[dest_si].extend(moving)
        for i, box in enumerate(moving):
            pos[box] = (dest_si, len(stacks[dest_si]) - k + i)
        ops.append((v, dest_si + 1))
        return k
    
    def carry_out(v):
        """Carry out box v. Must be at top of its stack and be the smallest remaining."""
        si, pi = pos[v]
        assert pi == len(stacks[si]) - 1, f"Box {v} not at top of stack {si}, at pos {pi}/{len(stacks[si])}"
        remove_top(si)
        ops.append((v, 0))
    
    # Greedy strategy with lookahead:
    # For each value v from 1 to n:
    #   If v is at top of its stack, carry it out.
    #   Otherwise, we need to move the boxes above v to some other stack.
    #   Choose the best destination stack.
    
    # Heuristic for choosing destination:
    # When moving a group of boxes G to stack S, the cost impact depends on
    # how many boxes in G are smaller than boxes currently in S that would be
    # below them after the move. Actually, since we're appending to the top,
    # all boxes in G will be above all existing boxes in S.
    # The key insight: after moving G to S, any box in G that is smaller than
    # some box in S's existing content doesn't matter (since G is on top).
    # What matters is: among the boxes in G, which ones can be carried out soon?
    # A box x in G can be carried out when all boxes above it in the new stack
    # have been removed. Since G is appended to S, the boxes in G maintain their
    # relative order. So within G, they can be carried out from top to bottom.
    # But boxes in S below G don't block G.
    # 
    # Better heuristic: minimize the total "blocking" effect.
    # When we place G on top of S, the boxes in G form a sub-stack.
    # The number of future moves needed to extract all boxes from this combined
    # structure depends on the interleaving of values.
    # 
    # Simple effective heuristic: choose the destination stack that minimizes
    # the number of boxes in G that are NOT in ascending order relative to
    # what's already there... actually let me think differently.
    # 
    # Key observation: the total energy is sum of (k+1) for each move operation.
    # To minimize total energy, we want to minimize both the number of moves
    # and the size of each move.
    # 
    # Strategy: when we need to unblock box v by moving boxes above it,
    # choose the destination that allows those moved boxes to be extracted
    # with minimal additional moves later.
    # 
    # A good proxy: prefer destinations where the moved group's boxes are
    # already in a favorable order, or where the destination stack has fewer
    # boxes (less potential interference).
    # 
    # Let's use: score(dest) = number of inversions created, i.e., count of pairs
    # (a, b) in the moved group where a > b but a appears before b (a is below b).
    # Wait, that's internal to the group and doesn't change.
    # 
    # Actually the most important factor: after moving G to S, when we later
    # process boxes in G, we'll need to move boxes above each one. The cost
    # depends on how many boxes are above each box in G within the combined stack.
    # Since G is on top of S, only boxes within G above a given box matter.
    # So the internal structure of G determines future costs, regardless of S.
    # The choice of S only affects whether boxes in S below G cause issues -
    # but they don't, because G is on top.
    # 
    # Wait, I think I'm overcomplicating. Let me reconsider.
    # 
    # After moving G (boxes from position p to end of source stack) to dest stack D:
    # - Source stack loses those boxes
    # - Dest stack gains those boxes on top
    # - Future operations on boxes in G depend only on G's internal ordering
    # - Future operations on boxes in D's original content are unaffected (they're below G)
    # 
    # So the choice of destination doesn't affect future costs for boxes in G!
    # It only affects: does choosing this destination create problems for
    # extracting boxes from the destination stack's original content? No, because
    # G is on top, so original content is still accessible once G is cleared.
    # 
    # Hmm, but there IS an effect: if we keep moving things to the same stack,
    # it grows very tall, and eventually moving things off it becomes expensive.
    # So we should distribute moves across stacks to keep them balanced.
    # 
    # Revised strategy: choose the shortest destination stack (as c0 does),
    # BUT with a tiebreaker that considers the top box of the destination.
    # Prefer destinations whose top box is LARGER than the bottom of G,
    # because then when we eventually clear G, the destination's original
    # top is exposed sooner without extra moves.
    # 
    # Actually wait - I realize the real issue. Let me re-examine.
    # 
    # The real cost driver: every time we need to access a box that's buried,
    # we must move everything above it. The total number of times a box gets
    # moved determines the total energy.
    # 
    # Optimal strategy insight: think of it as sorting. We need to extract
    # boxes in order 1, 2, ..., n. Each extraction may require moving a prefix
    # of a stack to another location.
    # 
    # This is similar to the problem of sorting with multiple stacks where
    # you can only access the top. The minimum number of moves relates to
    # the structure of the initial configuration.
    # 
    # For now, let's try a slightly better heuristic than c0:
    # 1. Always try to carry out the smallest available box first.
    # 2. When moving, prefer the destination stack that minimizes the
    #    maximum height after the move (load balancing).
    # 3. Among equally-balanced options, prefer the one with the largest
    #    top element (so smaller elements in the moved group aren't blocked).
    #    Wait, that's backwards - we want the destination's top to be small
    #    so that... no. Let me think again.
    # 
    # Actually, I think the simplest improvement is: instead of always moving
    # ALL boxes above v, consider whether we can avoid the move entirely by
    # having arranged things better earlier. But since we process in order,
    # we can't really do that.
    # 
    # Let me try a different approach: simulate and track which choices lead
    # to fewer total moves. Use a simple greedy with local optimization.
    
    # Actually, let me just improve the destination selection:
    # Score each candidate destination by: (resulting_height, -top_value)
    # i.e., prefer shorter resulting stacks, and among ties, prefer larger tops.
    
    for v in range(1, n + 1):
        info = find_box(v)
        if info is None:
            continue  # Already carried out (shouldn't happen if we process in order)
        si, pi = info
        if pi == len(stacks[si]) - 1:
            # Box v is at top, carry it out
            carry_out(v)
        else:
            # Need to move boxes above v
            num_above = len(stacks[si]) - pi - 1
            # Choose best destination
            best_dest = -1
            best_score = None
            for d in range(m):
                if d == si:
                    continue
                new_height = len(stacks[d]) + num_above + 1  # +1 for box v itself? No, v stays
                # Wait, we move boxes ABOVE v, not including v
                # So we move stacks[si][pi+1:] to dest
                moved_count = num_above
                new_height = len(stacks[d]) + moved_count
                # Score: prefer lower new_height, then higher top of dest
                top_val = stacks[d][-1] if stacks[d] else 0
                score = (new_height, -top_val)
                if best_score is None or score < best_score:
                    best_score = score
                    best_dest = d
            
            # Move boxes above v to best_dest
            # The box to specify in the operation is the topmost box being moved
            # which is stacks[si][pi+1] (the first box above v)
            top_moved = stacks[si][pi + 1]
            move_above(top_moved, best_dest)
            # Now v should be at top of si
            # Carry out v
            carry_out(v)
    
    # Output
    out_lines = []
    for v, i in ops:
        out_lines.append(f"{v} {i}")
    print("\n".join(out_lines))

solve()
