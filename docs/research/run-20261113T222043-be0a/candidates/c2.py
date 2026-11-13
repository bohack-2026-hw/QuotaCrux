import sys

def main():
    buf = sys.stdin.buffer
    # Read all data at once
    data = buf.read()
    # Split into lines; skip header (first line)
    lines = data.split(b'\n')
    # First line is header 'key,value', skip it
    # Last element may be empty if file ends with newline
    
    counts = {}  # key -> [count, sum]
    
    for i in range(1, len(lines)):
        line = lines[i]
        if not line:
            continue
        comma_pos = line.find(b',')
        key = line[:comma_pos]
        val = int(line[comma_pos+1:])
        entry = counts.get(key)
        if entry is not None:
            entry[0] += 1
            entry[1] += val
        else:
            counts[key] = [1, val]
    
    # Output
    out = sys.stdout.buffer
    out.write(b'key,count,sum\n')
    
    sorted_keys = sorted(counts)
    lines_out = []
    for key in sorted_keys:
        entry = counts[key]
        lines_out.append(key + b',' + str(entry[0]).encode() + b',' + str(entry[1]).encode() + b'\n')
    out.write(b''.join(lines_out))

if __name__ == '__main__':
    main()