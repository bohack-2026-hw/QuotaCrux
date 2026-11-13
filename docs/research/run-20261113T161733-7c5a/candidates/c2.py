import sys

def main():
    data = sys.stdin.buffer.read()
    idx = data.index(b'\n', 0)
    counts = {}
    sums = {}
    n = len(data)
    i = idx + 1
    while i < n:
        j = data.index(b',', i)
        key = data[i:j]
        k = data.index(b'\n', j)
        val = int(data[j+1:k])
        c = counts.get(key)
        if c is None:
            counts[key] = 1
            sums[key] = val
        else:
            counts[key] = c + 1
            sums[key] = sums[key] + val
        i = k + 1

    out = [b'key,count\n']
    for key in sorted(counts):
        out.append(key + b',' + str(counts[key]).encode() + b',' + str(sums[key]).encode() + b'\n')
    sys.stdout.buffer.write(b''.join(out))

if __name__ == '__main__':
    main()