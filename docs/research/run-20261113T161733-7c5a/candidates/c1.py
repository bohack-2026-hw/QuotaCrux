import sys

def main():
    data = sys.stdin.buffer.read()
    idx = data.index(b'\n')
    counts = {}
    sums = {}
    n = len(data)
    i = idx + 1
    while i < n:
        j = data.index(b',', i)
        key = data[i:j]
        k = data.index(b'\n', j)
        val = int(data[j+1:k])
        if key in counts:
            counts[key] += 1
            sums[key] += val
        else:
            counts[key] = 1
            sums[key] = val
        i = k + 1

    out_lines = [b'key,count,sum\n']
    for key in sorted(counts):
        out_lines.append(b'%s,%d,%d\n' % (key, counts[key], sums[key]))
    sys.stdout.buffer.write(b''.join(out_lines))

if __name__ == '__main__':
    main()