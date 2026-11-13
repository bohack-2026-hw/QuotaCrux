import sys


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b"\n")
    acc = {}
    get = acc.get
    for line in lines[1:]:
        if not line:
            continue
        k, v = line.split(b",")
        s = get(k)
        if s is None:
            acc[k] = [1, int(v)]
        else:
            s[0] += 1
            s[1] += int(v)
    out = [b"key,count,sum"]
    for k in sorted(acc):
        c, t = acc[k]
        out.append(b"%s,%d,%d" % (k, c, t))
    sys.stdout.buffer.write(b"\n".join(out) + b"\n")


main()
