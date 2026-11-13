import sys

def main():
    sys.set_int_max_str_digits(0)
    data = sys.stdin.buffer.read()
    # Split into lines by \n, skip header
    lines = data.split(b'\n')
    # Last element is empty (trailing \n); skip header at [0]
    del lines[0]
    # Remove trailing empty element if present
    if lines and lines[-1] == b'':
        del lines[-1]
    lines.sort()
    
    out = [b'key,count,sum\n']
    append = out.append
    i = 0
    n = len(lines)
    while i < n:
        comma = lines[i].find(b',')
        key = lines[i][:comma]
        total = int(lines[i][comma+1:])
        count = 1
        i += 1
        while i < n:
            comma2 = lines[i].find(b',')
            if lines[i][:comma2] != key:
                break
            total += int(lines[i][comma2+1:])
            count += 1
            i += 1
        append(key + b',' + str(count).encode() + b',' + str(total).encode() + b'\n')
    
    sys.stdout.buffer.write(b''.join(out))

if __name__ == '__main__':
    main()