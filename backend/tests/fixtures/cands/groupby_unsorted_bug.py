import sys
from itertools import groupby


def main():
    lines = sys.stdin.buffer.read().split(b"\n")[1:]
    rows = (l.split(b",") for l in lines if l)
    out = [b"key,count,sum"]
    for k, g in groupby(rows, key=lambda r: r[0]):
        vs = [int(r[1]) for r in g]
        out.append(b"%s,%d,%d" % (k, len(vs), sum(vs)))
    sys.stdout.buffer.write(b"\n".join(out) + b"\n")


main()
