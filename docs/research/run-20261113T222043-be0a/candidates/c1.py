import sys


def main():
    sys.set_int_max_str_digits(0)
    source = sys.stdin.buffer
    source.readline()
    groups = {}
    for line in source.read().splitlines():
        key, value = line.split(b',', 1)
        try:
            entry = groups[key]
        except KeyError:
            groups[key] = [1, int(value)]
        else:
            entry[0] += 1
            entry[1] += int(value)

    parts = [b'key,count,sum\n']
    for key in sorted(groups):
        count, total = groups[key]
        parts.append(b'%s,%d,%d\n' % (key, count, total))
    sys.stdout.buffer.write(b''.join(parts))


if __name__ == '__main__':
    main()
