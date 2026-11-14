import sys

def solve():
    input_data = sys.stdin.buffer.read().split()
    if not input_data:
        return
    it = iter(input_data)
    n = int(next(it))
    m = int(next(it))
    h = n // m
    
    # stacks[i] is a list of box numbers from bottom to top
    stacks = []
    for _ in range(m):
        stack = [int(next(it)) for _ in range(h)]
        stacks.append(stack)
    
    # position[v] = (stack_index, depth) where depth 0 is the bottom
    pos = {}
    for i in range(m):
        for j, v in enumerate(stacks[i]):
            pos[v] = (i, j)
    
    ops = []
    
    def move(v, dest_idx):
        """Move box v and all boxes above it to dest_idx."""
        src_idx, depth = pos[v]
        if src_idx == dest_idx:
            return False
        
        # The segment being moved
        segment = stacks[src_idx][depth:]
        k = len(segment)
        
        ops.append((segment[0], dest_idx + 1))
        
        # Update state
        del stacks[src_idx][depth:]
        stacks[dest_idx].extend(segment)
        
        for idx, val in enumerate(segment):
            pos[val] = (dest_idx, len(stacks[dest_idx]) - k + idx)
        
        return True
    
    def carry_out(v):
        """Carry out box v. It must be at the top of its stack."""
        src_idx, depth = pos[v]
        assert depth == len(stacks[src_idx]) - 1, f"Box {v} is not at top!"
        
        ops.append((v, 0))
        
        del stacks[src_idx][depth]
        del pos[v]
    
    for value in range(1, n + 1):
        src_idx, depth = pos[value]
        
        if depth < len(stacks[src_idx]) - 1:
            # Need to move boxes above 'value'
            # Choose destination stack that minimizes future cost.
            # Heuristic: Move to the shortest stack (excluding source).
            # This tends to keep stacks balanced and allows deeper items to be accessed sooner.
            
            # Let's try a slightly smarter heuristic:
            # We want to minimize the number of moves. 
            # Moving a block of size K costs K+1 energy.
            # If we move it to a stack of height H, the new height is H+K.
            # The item 'value' will now be at depth H+K-1 in the new stack? No.
            # 'value' is the bottom of the moved segment.
            # So 'value' becomes the (H)-th item (0-indexed) in the destination stack? No.
            # Destination stack has H items. We append K items.
            # 'value' is the first of the K items appended.
            # So 'value' is at index H in the destination stack.
            # To access 'value', we need to remove H+K-1 items above it? No.
            # Items above 'value' in the destination stack are the other K-1 items from the segment.
            # Wait, the segment is moved as a whole. The relative order is preserved.
            # So 'value' is still below the other K-1 items.
            # Thus, moving 'value' doesn't expose it unless K=1.
            # If K > 1, we still have K-1 boxes on top of 'value'.
            
            # Therefore, we should ideally move the smallest possible block that exposes 'value'? 
            # But we MUST move ALL boxes above 'value'. We can't just move some.
            # Operation 1 says: "Remove box v and all boxes above it... and move them".
            # So we are forced to move the entire suffix.
            
            # So the choice is only WHERE to put this suffix.
            # To minimize future work, we should place this suffix such that the boxes remaining in the source stack (which are smaller than 'value') can be accessed easily, AND the boxes in the destination stack don't create too much clutter.
            
            # Actually, the boxes in the source stack below 'value' are all smaller than 'value' (since we process in ascending order, any box smaller than 'value' must have been carried out already? NO. The boxes are labeled 1..n. We carry them out in ascending order. So when we are about to carry out 'value', all boxes 1..value-1 have ALREADY been carried out. 
            # This means the boxes remaining in the warehouse are all >= value.
            # In the source stack, the boxes below 'value' must be > value? 
            # Let's check. 
            # If a box x < value was in the source stack below 'value', it would have been carried out before 'value'. 
            # When x was carried out, it was at the top. 
            # So yes, all boxes currently in the stacks are >= current_value.
            # Specifically, in the source stack, the boxes below 'value' are all > value.
            # The boxes above 'value' are also all > value.
            
            # So we are moving a block of boxes all > value to another stack.
            # This doesn't help us carry out 'value' immediately unless the block is empty (which it isn't).
            # Wait, if I move the block above 'value', then 'value' becomes the top of the source stack.
            # Then I can carry out 'value'.
            
            # So the sequence is:
            # 1. Move suffix above 'value' to dest.
            # 2. Carry out 'value'.
            
            # The cost is (len(suffix) + 1) + 0.
            
            # To minimize total cost, we want len(suffix) to be small.
            # But len(suffix) is determined by the initial configuration and previous moves.
            # We cannot change len(suffix) for the current step, but our choice of 'dest' affects FUTURE steps.
            
            # By moving the suffix to a specific stack, we change the heights of the stacks.
            # Generally, keeping stacks short is good because it reduces the number of boxes you might have to move later.
            # However, if we move a large suffix to an empty stack, that stack becomes tall.
            
            # Let's stick with the heuristic: Move to the shortest stack (excluding source).
            # This balances the loads.
            
            candidates = [j for j in range(m) if j != src_idx]
            # Sort by length
            candidates.sort(key=lambda j: len(stacks[j]))
            dest_idx = candidates[0]
            
            move(value, dest_idx)
            
            # After moving, 'value' is at the top of src_idx
            # Verify
            assert pos[value][1] == len(stacks[src_idx]) - 1
        
        carry_out(value)
        
    # Output operations
    out_lines = []
    for v, i in ops:
        out_lines.append(f"{v} {i}")
    sys.stdout.write("\n".join(out_lines) + "\n")

if __name__ == "__main__":
    solve()