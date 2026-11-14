import sys

def deserialize_stdin(input_str):
    input_str = input_str.strip()
    if input_str == "":
        return []
    return list(map(int, input_str.split(',')))

def serialize_stdout(result):
    return str(result)

def maximumStrongPairXor(nums):
    # nums[i] <= 100, so max bit is 6 (2^6 = 64, 2^7 = 128)
    # We can use a greedy approach from the highest bit down.
    # Let ans be the maximum XOR value we've found so far for higher bits.
    # For bit k, we want to see if there's a pair (x, y) such that:
    # 1. x and y have different bits at position k.
    # 2. The prefix of x and y above bit k matches the prefix of 'ans' (shifted).
    # 3. |x - y| <= min(x, y). Since x, y are in the set, we can just check if such a pair exists in the original set.
    
    # Actually, a simpler observation for small N and small values:
    # The condition |x - y| <= min(x, y) is equivalent to max(x, y) <= 2 * min(x, y).
    # If we sort unique numbers, for each i, j must satisfy nums[j] <= 2 * nums[i].
    
    # Given constraints are very small (N<=50, V<=100), the original O(N^2) is already fast.
    # However, to ensure speedup, we can try to prune or use a smarter check.
    # But wait, Python overhead is high. Maybe just optimizing the loop structure helps?
    # Or maybe using a set for lookups?
    
    # Let's stick to the optimized O(N^2) but with minimal overhead, or try the bitwise greedy.
    # Bitwise greedy is O(V * log V) which is ~ 100 * 7 = 700 operations.
    # O(N^2) is 50 * 50 = 2500 operations.
    # So bitwise greedy should be faster if implemented correctly.
    
    unique_nums = set(nums)
    ans = 0
    
    # Max value is 100, so bits up to 6 (2^6=64). 2^7=128 > 100.
    for k in range(6, -1, -1):
        # Try to set bit k in ans
        candidate_ans = ans | (1 << k)
        
        # Check if there exists x, y in unique_nums such that:
        # (x ^ y) has the same prefix as candidate_ans for bits > k,
        # and bit k is 1.
        # This is equivalent to checking if there exist x, y such that:
        # x >> k and y >> k differ by exactly 1 (one has 0, one has 1 at bit k, same above)
        # AND the lower bits don't matter for the existence of the prefix match?
        # No, the standard algorithm checks if there's a pair whose XOR is consistent with candidate_ans.
        
        # A more direct way for this specific problem:
        # We know x, y must be in unique_nums.
        # We want max x^y subject to max(x,y) <= 2*min(x,y).
        
        # Let's iterate through possible prefixes.
        # Actually, since N is small, let's just do the double loop but break early efficiently.
        # The previous solution did: sorted(set(nums)).
        # Let's optimize the inner loop.
        
        pass 
    
    # Re-evaluating: Is bitwise greedy easy here?
    # Standard max XOR pair doesn't have the strong constraint.
    # With strong constraint, it's harder to do purely bitwise greedy without checking validity.
    
    # Let's go back to O(N^2) but optimized.
    # Sort unique nums.
    u = sorted(unique_nums)
    n = len(u)
    res = 0
    for i in range(n):
        # Optimization: if u[i] is large, the range of valid j is smaller.
        # Also, we can precompute something?
        # Just tight loop.
        limit = u[i] * 2
        for j in range(i + 1, n):
            if u[j] > limit:
                break
            val = u[i] ^ u[j]
            if val > res:
                res = val
    return res

input_data = sys.stdin.read().strip()
nums = deserialize_stdin(input_data)
ans = maximumStrongPairXor(nums)
sys.stdout.write(serialize_stdout(ans))