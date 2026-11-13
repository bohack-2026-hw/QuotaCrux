import csv
import gc
import sys


def main():
    sys.set_int_max_str_digits(0)
    csv.field_size_limit(sys.maxsize)
    gc.disable()
    reader = csv.reader(sys.stdin)
    next(reader, None)
    groups = {}
    get = groups.get
    to_int = int
    for key, raw_value in reader:
        value = to_int(raw_value)
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
