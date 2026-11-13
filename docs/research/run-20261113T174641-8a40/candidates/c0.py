import csv
import sys


def main():
    reader = csv.reader(sys.stdin)
    next(reader, None)  # header: key,value
    counts = {}
    sums = {}
    for row in reader:
        key = row[0]
        value = int(row[1])
        if key in counts:
            counts[key] += 1
            sums[key] += value
        else:
            counts[key] = 1
            sums[key] = value

    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["key", "count", "sum"])
    for key in sorted(counts):
        writer.writerow([key, counts[key], sums[key]])


if __name__ == "__main__":
    main()
