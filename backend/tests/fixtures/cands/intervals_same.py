# identical algorithm to the initial program: correct, no gain
import csv
import sys


def main():
    reader = csv.reader(sys.stdin)
    next(reader, None)  # header: start,end
    intervals = [(int(row[0]), int(row[1])) for row in reader]
    intervals.sort()

    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])

    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["start", "end"])
    writer.writerows(merged)


if __name__ == "__main__":
    main()
