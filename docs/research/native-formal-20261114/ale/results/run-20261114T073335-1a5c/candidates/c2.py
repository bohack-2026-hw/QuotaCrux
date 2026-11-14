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
    
    for value in range(1, n + 1):
        src, pos = box_pos[value]
        if pos + 1 < len(stacks[src]):
            # 需要移动value上方的所有箱子
            above_boxes = stacks[src][pos + 1:]
            # 选择目的地：优先选择包含较小未取出箱子的栈，或空栈
            dest_candidates = []
            for j in range(m):
                if j == src:
                    continue
                # 计算该栈中最小的未取出箱子编号
                min_box_in_dest = float('inf')
                for box in stacks[j]:
                    if box >= value:  # 还未取出的箱子
                        min_box_in_dest = min(min_box_in_dest, box)
                        break
                # 优先级：1. 空栈 2. 包含较小箱子的栈 3. 栈长度短
                priority = (
                    0 if len(stacks[j]) == 0 else 1,
                    min_box_in_dest if min_box_in_dest != float('inf') else float('inf'),
                    len(stacks[j])
                )
                dest_candidates.append((priority, j))
            
            if dest_candidates:
                dest_candidates.sort()
                dest = dest_candidates[0][1]
                
                # 执行移动操作
                k = len(above_boxes)
                operations.append((above_boxes[0], dest + 1))
                
                # 更新状态
                moved_boxes = above_boxes
                stacks[dest].extend(moved_boxes)
                del stacks[src][pos + 1:]
                
                # 更新box_pos
                for new_pos, box in enumerate(moved_boxes):
                    box_pos[box] = (dest, len(stacks[dest]) - len(moved_boxes) + new_pos)
        
        # 取出箱子value
        operations.append((value, 0))
        stacks[src].pop()
        del box_pos[value]
    
    # 输出操作序列
    out_lines = [f"{v} {i}" for v, i in operations]
    print("\n".join(out_lines))

solve()