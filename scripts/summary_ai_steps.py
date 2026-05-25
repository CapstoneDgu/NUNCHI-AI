import re
import sys
from collections import defaultdict


LOG_PATTERN = re.compile(
    r"\[AI_STEP\].*?step=(?P<step>[a-zA-Z0-9_./:-]+).*?elapsedMs=(?P<elapsed>\d+)"
)


def parse_log(file_path: str):
    stats = defaultdict(list)

    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        for line in file:
            match = LOG_PATTERN.search(line)
            if not match:
                continue

            step = match.group("step")
            elapsed = int(match.group("elapsed"))
            stats[step].append(elapsed)

    return stats


def print_summary(stats):
    if not stats:
        print("No [AI_STEP] logs found.")
        return

    rows = []

    for step, values in stats.items():
        count = len(values)
        avg = sum(values) / count
        max_value = max(values)
        min_value = min(values)

        rows.append((step, count, avg, max_value, min_value))

    rows.sort(key=lambda x: x[2], reverse=True)

    print()
    print("AI_STEP Summary")
    print("-" * 80)
    print(f"{'step':35} {'count':>8} {'avg(ms)':>12} {'max(ms)':>12} {'min(ms)':>12}")
    print("-" * 80)

    for step, count, avg, max_value, min_value in rows:
        print(f"{step:35} {count:8d} {avg:12.2f} {max_value:12d} {min_value:12d}")

    print("-" * 80)


def main():
    file_path = sys.argv[1] if len(sys.argv) > 1 else "logs/fastapi.log"
    stats = parse_log(file_path)
    print_summary(stats)


if __name__ == "__main__":
    main()