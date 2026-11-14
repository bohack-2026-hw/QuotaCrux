import sys


def main():
    stats = {}
    get = stats.get
    for line in sys.stdin.buffer:
        stamp, method, path, status, latency_text = line.split()
        key = (stamp[:13], method, path)
        latency = int(latency_text)
        error = status[0] == 53
        entry = get(key)
        if entry is None:
            stats[key] = [1, int(error), latency, latency]
        else:
            entry[0] += 1
            entry[1] += error
            entry[2] += latency
            if latency > entry[3]:
                entry[3] = latency

    rows = ['hour,method,path,count,errors,sum_ms,max_ms']
    append = rows.append
    for key in sorted(stats):
        count, errors, total, maximum = stats[key]
        hour, method, path = key
        append(f'{hour.decode()},{method.decode()},{path.decode()},{count},{errors},{total},{maximum}')
    sys.stdout.write('\n'.join(rows) + '\n')


if __name__ == '__main__':
    main()
