import re
import sys
from datetime import datetime

LINE = re.compile(r"^(\S+) (DELETE|GET|PATCH|POST|PUT) (\S+) (\d{3}) (\d+)$")


def main():
    stats = {}
    for line in sys.stdin:
        match = LINE.match(line.rstrip("\n"))
        if match is None:
            continue
        stamp, method, path, status, latency = match.groups()
        hour = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H")
        key = (hour, method, path)
        latency = int(latency)
        entry = stats.get(key)
        if entry is None:
            entry = stats[key] = {"count": 0, "errors": 0, "sum": 0, "max": 0}
        entry["count"] += 1
        if int(status) >= 500:
            entry["errors"] += 1
        entry["sum"] += latency
        entry["max"] = max(entry["max"], latency)

    out = sys.stdout
    out.write("hour,method,path,count,errors,sum_ms,max_ms\n")
    for key in sorted(stats):
        e = stats[key]
        out.write(f"{key[0]},{key[1]},{key[2]},{e['count']},{e['errors']},{e['sum']},{e['max']}\n")


if __name__ == "__main__":
    main()
