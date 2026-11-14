import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    stacks = []
    idx = 2
    for i in range(m):
        stack = data[idx:idx + n // m]
        stacks.append(stack)
        idx += n // m
    
    # 记录每个箱子所在的栈和位置
    box_pos = {}  # box -> (stack_idx, position_in_stack)
    for i, stack in enumerate(stacks):
        for j, box in enumerate(stack):
            box_pos[box] = (i, j)
    
    operations = []
    
    def future_cost(box, dest_stack_idx):
        """计算箱子box如果移到dest_stack_idx后，在被取出前还需要被移动的次数"""
        if box not in box_pos:
            return 0
        # 找到box在dest_stack_idx中的位置
        if dest_stack_idx is None:
            return 0
        dest_stack = stacks[dest_stack_idx]
        try:
            pos_in_dest = dest_stack.index(box)
        except ValueError:
            return 0
        # box上方的箱子数
        above_count = len(dest_stack) - pos_in_dest - 1
        # 这些上方箱子中，有多少个编号小于box（它们会在box之前被取出）
        smaller_above = sum(1 for b in dest_stack[pos_in_dest+1:] if b < box and b in box_pos)
        # box需要被移动的次数至少是smaller_above（每次上面有一个较小箱子被取出时，如果box不在顶部就需要移动）
        # 但实际上，如果box上面的箱子都被移走了，box就不需要再移动了
        # 简化估计：box需要被移动的次数约为above_count/2（平均情况）
        return above_count // 2
    
    for value in range(1, n + 1):
        src, pos = box_pos[value]
        if pos + 1 < len(stacks[src]):
            # 需要移动value上方的所有箱子
            above_boxes = stacks[src][pos + 1:]
            
            # 评估每个候选目的地的未来成本
            best_dest = None
            best_cost = float('inf')
            for j in range(m):
                if j == src:
                    continue
                # 计算将above_boxes移到j后的未来成本
                total_future_cost = 0
                for box in above_boxes:
                    # 假设box被移到j后，它在j中的位置是len(stacks[j]) + index_in_above
                    # 简化：直接计算当前j栈中比box小的箱子数量
                    smaller_in_j = sum(1 for b in stacks[j] if b < box and b in box_pos)
                    total_future_cost += smaller_in_j
                
                # 也考虑当前栈长度（较短的栈通常更好）
                current_len_penalty = len(stacks[j]) * 0.1
                
                total_cost = total_future_cost + current_len_penalty
                
                if total_cost < best_cost:
                    best_cost = total_cost
                    best_dest = j
            
            if best_dest is not None:
                # 执行移动操作
                operations.append((above_boxes[0], best_dest + 1))
                
                # 更新状态
                moved_boxes = above_boxes
                stacks[best_dest].extend(moved_boxes)
                del stacks[src][pos + 1:]
                
                # 更新box_pos
                base_pos = len(stacks[best_dest]) - len(moved_boxes)
                for new_pos, box in enumerate(moved_boxes):
                    box_pos[box] = (best_dest, base_pos + new_pos)
        
        # 取出箱子value
        operations.append((value, 0))
        stacks[src].pop()
        del box_pos[value]
    
    # 输出操作序列
    out_lines = [f"{v} {i}" for v, i in operations]
    print("\n".join(out_lines))

solve()