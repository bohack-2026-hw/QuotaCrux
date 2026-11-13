import sys


def main():
    sys.set_int_max_str_digits(0)
    lines = iter(sys.stdin.read().splitlines())
    next(lines, None)
    groups = {}
    get = groups.get
    to_int = int
    for line in lines:
        key, value = line.split(',', 1)
        value = to_int(value)
        entry = get(key)
        if entry is None:
            groups[key] = [1, value]
        else:
            entry[0] += 1
            entry[1] += value

    output = ['key,count,sum\n']
    append = output.append
    for key in sorted(groups):
        count, total = groups[key]
        append(f'{key},{count},{total}\n')
    sys.stdout.write(''.join(output))


if __name__ == '__main__':
    main()
