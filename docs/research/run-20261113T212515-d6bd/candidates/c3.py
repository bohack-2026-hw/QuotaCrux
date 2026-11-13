import re
import sys


def main():
    sys.set_int_max_str_digits(0)
    source = sys.stdin
    source.readline()
    data = source.read()
    runs = re.findall(r'([^,\n]+),([^\n]+\n(?:\1,[^\n]+\n)*)', data)
    del data
    runs.sort()

    parts = ['key,count,sum\n']
    append = parts.append
    previous = None
    count = 0
    total = 0
    for key, raw_values in runs:
        values = raw_values.split('\n' + key + ',')
        run_count = len(values)
        run_total = sum(map(int, values))
        if key == previous:
            count += run_count
            total += run_total
        else:
            if previous is not None:
                append(f'{previous},{count},{total}\n')
            previous = key
            count = run_count
            total = run_total
    if previous is not None:
        append(f'{previous},{count},{total}\n')
    sys.stdout.write(''.join(parts))


if __name__ == '__main__':
    main()
