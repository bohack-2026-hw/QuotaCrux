import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]

# 建立位置映射以便快速查找
pos_map = {}
for i, stack in enumerate(stacks):
    for j, val in enumerate(stack):
        pos_map[val] = (i, j)

operations = []
energy = 0

for value in range(1, n + 1):
    src_i, src_j = pos_map[value]
    if src_j + 1 < len(stacks[src_i]):
        # 需要移动上面的箱子
        above = stacks[src_i][src_j + 1:]
        
        # 选择目标堆栈：优先选择空的或较短的堆栈
        # 更好的策略：选择能最小化未来移动的堆栈
        best_dest = -1
        best_score = float('inf')
        
        for dest_i in range(m):
            if dest_i == src_i:
                continue
            
            # 计算将above移动到dest_i后的效果
            new_len = len(stacks[dest_i]) + len(above)
            
            # 简单启发式：选择结果长度最小的堆栈
            score = new_len
            
            if score < best_score:
                best_score = score
                best_dest = dest_i
        
        operations.append((above[0], best_dest + 1))
        energy += len(above) + 1
        
        # 更新状态
        moved_boxes = stacks[src_i][src_j + 1:]
        del stacks[src_i][src_j + 1:]
        stacks[best_dest].extend(moved_boxes)
        
        # 更新pos_map
        for k, box in enumerate(moved_boxes):
            pos_map[box] = (best_dest, len(stacks[best_dest]) - len(moved_boxes) + k)
    
    operations.append((value, 0))
    
    # 移除value
    stacks[src_i].pop()
    del pos_map[value]
    
    # 更新剩余箱子的位置（简化处理）
    for i in range(m):
        for j in range(len(stacks[i])):
            pos_map[stacks[i][j]] = (i, j)

for v, i in operations:
    print(v, i)
