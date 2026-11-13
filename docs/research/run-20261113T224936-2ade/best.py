import sys

def main():
    inp = sys.stdin.buffer
    # Skip header
    first_line = inp.readline()  # 'key,value\n'
    
    # We need to group and sort keys
    # Use dict for count and sum
    counts = {}
    sums = {}
    
    for line in inp:
        # line is bytes ending with \n
        # Find the comma
        idx = line.rfind(b',')
        key = line[:idx]
        # value is idx+1 to end-1 (strip \n)
        val = int(line[idx+1:])
        if key in counts:
            counts[key] += 1
            sums[key] += val
        else:
            counts[key] = 1
            sums[key] = val
    
    out = sys.stdout.buffer
    out.write(b'key,count,sum\n')
    for key in sorted(counts):
        out.write(key + b',' + str(counts[key]).encode() + b',' + str(sums[key]).encode() + b'\n')

if __name__ == '__main__':
    main()