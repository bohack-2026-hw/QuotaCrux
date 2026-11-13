import sys


def main():
    sys.set_int_max_str_digits(0)
    lines = sys.stdin.read().splitlines()
    del lines[0]
    lines.sort()
    parts = ['key,count,sum\n']
    append = parts.append
    write = sys.stdout.write
    previous = None
    count = 0
    total = 0
    for line in lines:
        key, value = line.split(',', 1)
        value = int(value)
        if key == previous:
            count += 1
            total += value
        else:
            if previous is not None:
                append(f'{previous},{count},{total}\n')
                if len(parts) >= 4096:
                    write(''.join(parts))
                    parts.clear()
            previous = key
            count = 1
            total = value
    if previous is not None:
        append(f'{previous},{count},{total}\n')
    write(''.join(parts))


if __name__ == '__main__':
    main()
