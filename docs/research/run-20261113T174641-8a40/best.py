import sys

def main():
    data = sys.stdin.buffer.read()
    # Skip header line
    newline = data.find(b'\n')
    if newline == -1:
        # No header newline means empty input or just "key,value" with no newline
        print("key,count,sum")
        return
    rest = data[newline+1:]
    if not rest:
        print("key,count,sum")
        return

    # Use single dict mapping key -> [count, sum]
    # Parse lines manually for speed
    lines = rest.split(b'\n')
    agg = {}
    for line in lines:
        if not line:
            continue
        # Find first comma
        ci = line.find(b',')
        key = line[:ci]
        val = int(line[ci+1:])
        if key in agg:
            entry = agg[key]
            entry[0] += 1
            entry[1] += val
        else:
            agg[key] = [1, val]

    # Sort by key in Python string order
    # For bytes with [A-Za-z0-9_], byte order == Python string order
    out = []
    out.append(b"key,count,sum")
    for key in sorted(agg):
        cnt, s = agg[key]
        out.append(key + b"," + str(cnt).encode() + b"," + str(s).encode())
    sys.stdout.buffer.write(b'\n'.join(out) + b'\n')

if __name__ == "__main__":
    main()
