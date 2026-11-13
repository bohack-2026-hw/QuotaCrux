import sys

def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b'\n')
    
    counts = {}
    
    for i in range(1, len(lines)):
        line = lines[i]
        if not line:
            continue
        cp = line.rfind(b',')
        key = line[:cp]
        val = int(line[cp+1:])
        entry = counts.get(key)
        if entry is not None:
            entry[0] += 1
            entry[1] += val
        else:
            counts[key] = [1, val]
    
    out = sys.stdout.buffer
    n = len(counts)
    parts = [b'key,count,sum\n'] + [None] * n
    idx = 1
    for key in sorted(counts):
        e = counts[key]
        parts[idx] = key + b',' + str(e[0]).encode() + b',' + str(e[1]).encode() + b'\n'
        idx += 1
    out.write(b''.join(parts))

if __name__ == '__main__':
    main()
