import sys

def main():
    sys.set_int_max_str_digits(0)
    text = sys.stdin.read()
    lines = text.split('\n')
    # lines[0] is header 'key,value'; skip it
    groups = {}
    get = groups.get
    to_int = int
    for line in lines[1:]:
        if not line:
            continue
        comma_pos = line.index(',')
        key = line[:comma_pos]
        val = to_int(line[comma_pos+1:])
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
