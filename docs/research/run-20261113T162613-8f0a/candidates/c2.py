import sys

def main():
    sys.set_int_max_str_digits(0)
    text = sys.stdin.read()
    lines = text.splitlines()
    # lines[0] is header 'key,value'
    counts = {}
    sums = {}
    to_int = int
    get_c = counts.get
    get_s = sums.get
    for line in lines[1:]:
        if not line:
            continue
        comma = line.index(',')
        key = line[:comma]
        val = to_int(line[comma+1:])
        c = get_c(key)
        if c is None:
            counts[key] = 1
            sums[key] = val
        else:
            counts[key] = c + 1
            sums[key] = get_s(key) + val

    out = ['key,count,sum\n']
    append = out.append
    for key in sorted(counts):
        append(f'{key},{counts[key]},{sums[key]}\n')
    sys.stdout.write(''.join(out))

if __name__ == '__main__':
    main()