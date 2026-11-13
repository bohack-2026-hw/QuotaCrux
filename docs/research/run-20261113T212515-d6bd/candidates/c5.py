import sys

def main():
    sys.set_int_max_str_digits(0)
    data = sys.stdin.buffer.read()
    # Split by newline, skip header (first element)
    lines = data.split(b'\n')
    n = len(lines)
    # Remove header
    del lines[0]
    # Remove trailing empty element if present
    if lines and lines[-1] == b'':
        lines.pop()
    # Sort lines (full line sort works because comma < all key chars)
    lines.sort()
    
    out = [b'key,count,sum\n']
    append = out.append
    i = 0
    m = len(lines)
    while i < m:
        line = lines[i]
        cpos = line.find(b',')
        key = line[:cpos]
        total = int(line[cpos+1:])
        count = 1
        i += 1
        # Inner loop: accumulate consecutive same-key lines
        while i < m:
            line2 = lines[i]
            cpos2 = line2.find(b',')
            if line2[:cpos2] != key:
                break
            total += int(line2[cpos2+1:])
            count += 1
            i += 1
        append(key + b',' + str(count).encode() + b',' + str(total).encode() + b'\n')
    
    sys.stdout.buffer.write(b''.join(out))

if __name__ == '__main__':
    main()
