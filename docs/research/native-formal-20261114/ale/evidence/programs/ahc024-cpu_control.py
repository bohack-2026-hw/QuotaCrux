_work = 0
for _i in range(12000000):
    _work = (_work + _i) & 65535
import sys
lines = sys.stdin.read().splitlines()
print('\n'.join(lines[1:]))
