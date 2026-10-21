import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

LOG_PATTERN = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ '
    r'\[(?P<timestamp>[^\]]+)\] '
    r'"(?P<request>(?:[^"\\]|\\.)*)" '
    r'(?P<status>\d{3}) '
    r'(?P<size>\d+|-) '
    r'"(?P<referer>(?:[^"\\]|\\.)*)" '
    r'"(?P<user_agent>(?:[^"\\]|\\.)*)"$'
)


def parse_log_line(line):
    match = LOG_PATTERN.fullmatch(line.strip())

    if match is None:
        return None

    try:
        timestamp = datetime.strptime(
            match.group("timestamp"),
            "%d/%b/%Y:%H:%M:%S %z",
        )
        status = int(match.group("status"))

        if not 100 <= status <= 599:
            return None

        return {
            "ip": match.group("ip"),
            "timestamp": timestamp,
            "hour": timestamp.strftime("%Y-%m-%d %H:00 %z"),
            "status": status,
            "status_class": f"{status // 100}xx",
        }
    except ValueError:
        return None


def analyze_log(input_path, top_n):
    ip_counts = Counter()
    status_counts = Counter()
    hourly_counts = Counter()

    total_lines = 0
    valid_lines = 0
    invalid_lines = 0

    with Path(input_path).open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            total_lines += 1
            record = parse_log_line(line)

            if record is None:
                invalid_lines += 1
                continue

            valid_lines += 1
            ip_counts[record["ip"]] += 1
            status_counts[record["status_class"]] += 1
            hourly_counts[record["hour"]] += 1

    peak_count = max(hourly_counts.values(), default=0)
    peak_hours = sorted(
        hour
        for hour, count in hourly_counts.items()
        if count == peak_count and peak_count > 0
    )

    return {
        "input_file": str(input_path),
        "total_lines": total_lines,
        "valid_lines": valid_lines,
        "invalid_lines": invalid_lines,
        "top_ips": [
            {"ip": ip, "requests": count}
            for ip, count in sorted(
                ip_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:top_n]
        ],
        "status_classes": {
            status_class: status_counts.get(status_class, 0)
            for status_class in ("1xx", "2xx", "3xx", "4xx", "5xx")
        },
        "hourly_requests": dict(sorted(hourly_counts.items())),
        "peak_hours": [
            {"hour": hour, "requests": peak_count}
            for hour in peak_hours
        ],
    }


def format_text_report(report):
    lines = [
        "ЗВІТ ПРО АНАЛІЗ ЖУРНАЛУ ВЕБСЕРВЕРА",
        "=" * 45,
        f"Вхідний файл: {report['input_file']}",
        f"Усього рядків: {report['total_lines']}",
        f"Коректних рядків: {report['valid_lines']}",
        f"Пошкоджених рядків: {report['invalid_lines']}",
        "",
        "ТОП IP-АДРЕС ЗА КІЛЬКІСТЮ ЗАПИТІВ",
    ]

    if report["top_ips"]:
        for index, item in enumerate(report["top_ips"], start=1):
            lines.append(
                f"{index}. {item['ip']} — {item['requests']} запитів"
            )
    else:
        lines.append("Немає коректних записів.")

    lines.extend(["", "РОЗПОДІЛ КОДІВ ВІДПОВІДІ"])

    for status_class, count in report["status_classes"].items():
        lines.append(f"{status_class}: {count}")

    lines.extend(["", "КІЛЬКІСТЬ ЗАПИТІВ ЗА ГОДИНАМИ"])

    if report["hourly_requests"]:
        for hour, count in report["hourly_requests"].items():
            lines.append(f"{hour}: {count}")
    else:
        lines.append("Немає коректних записів.")

    lines.extend(["", "ГОДИНИ ПІКОВОГО НАВАНТАЖЕННЯ"])

    if report["peak_hours"]:
        for item in report["peak_hours"]:
            lines.append(
                f"{item['hour']} — {item['requests']} запитів"
            )
    else:
        lines.append("Немає даних для визначення пікового навантаження.")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Аналіз журналів вебсервера у форматі Combined Log Format."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Шлях до вхідного журналу.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Шлях до вихідного звіту.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Формат звіту: text або json.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Кількість IP-адрес у топі.",
    )

    args = parser.parse_args()

    if args.top < 1:
        parser.error("Параметр --top повинен бути додатним числом.")

    try:
        report = analyze_log(args.input, args.top)

        if args.format == "json":
            content = json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            ) + "\n"
        else:
            content = format_text_report(report)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

    except OSError as error:
        parser.exit(1, f"Помилка роботи з файлом: {error}\n")

    print(f"Звіт збережено: {args.output}")
    print(f"Коректних рядків: {report['valid_lines']}")
    print(f"Пошкоджених рядків: {report['invalid_lines']}")


if __name__ == "__main__":
    main()
