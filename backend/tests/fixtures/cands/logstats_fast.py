import sys
def main():
    stats = {}
    get = stats.get
    for line in sys.stdin.buffer.read().decode().splitlines():
        ts, method, path, status, lat = line.split(" ")
        key = (ts[:13], method, path)
        lat = int(lat)
        e = get(key)
        if e is None:
            stats[key] = [1, status[0] == "5", lat, lat]
        else:
            e[0] += 1
            if status[0] == "5":
                e[1] += 1
            e[2] += lat
            if lat > e[3]:
                e[3] = lat
    out = ["hour,method,path,count,errors,sum_ms,max_ms"]
    for k in sorted(stats):
        c, er, s, m = stats[k]
        out.append(f"{k[0]},{k[1]},{k[2]},{c},{int(er)},{s},{m}")
    sys.stdout.write("\n".join(out) + "\n")
main()
