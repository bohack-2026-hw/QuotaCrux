import sys

def main():
    sys.set_int_max_str_digits(0)
    lines = iter(sys.stdin.read().splitlines())
    next(lines, None)
    groups = {}
    get = groups.get
    to_int = int
    for line in lines:
        idx = line.index(',')
        key = line[:idx]
        val = to_int(line[idx+1:])
        entry = get(key)
        if entry is None:
            groups[key] = [1, val]
        else:
            entry[0] += 1
            entry[1] += val

    out = ['key,count,sum\n']
    append = out.append
    for key in sorted(groups):
        count, total = groups[key]
        append(f'{key},{count},{total}\n')
    sys.stdout.write(''.join(out))

if __name__ == '__main__':
    main()