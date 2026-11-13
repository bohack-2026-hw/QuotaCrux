import sys
from itertools import groupby


def main():
    rows = sys.stdin.buffer.read().split(b"\n")[1:]
    if rows and rows[-1] == b"":
        rows.pop()
    pairs = [r.split(b",") for r in rows]
    out = [b"key,count,sum"]
    if all(a[0] <= b[0] for a, b in zip(pairs, pairs[1:])):
        for k, g in groupby(pairs, key=lambda p: p[0]):
            vs = [int(p[1]) for p in g]
            out.append(b"%s,%d,%d" % (k, len(vs), sum(vs)))
    else:
        acc = {}
        for k, v in pairs:
            s = acc.get(k)
            if s is None:
                acc[k] = [1, int(v)]
            else:
                s[0] += 1
                s[1] += int(v)
        out += [b"%s,%d,%d" % (k, c, t) for k, (c, t) in sorted(acc.items())]
    sys.stdout.buffer.write(b"\n".join(out) + b"\n")


main()
