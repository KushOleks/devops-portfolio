#!/usr/bin/env python3

import argparse
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_CONFIG = 2


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def classify_error(exc):
    if isinstance(exc, ssl.SSLCertVerificationError):
        return "SSL_ERROR", str(exc)

    if isinstance(exc, ConnectionRefusedError):
        return "CONNECTION_REFUSED", str(exc)

    if isinstance(exc, socket.gaierror):
        return "DNS_ERROR", str(exc)

    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "TIMEOUT", str(exc)

    if isinstance(exc, ssl.SSLError):
        return "SSL_ERROR", str(exc)

    if isinstance(exc, OSError):
        if exc.errno in (61, 111):
            return "CONNECTION_REFUSED", str(exc)

    return "NETWORK_ERROR", str(exc)


def check_endpoint(endpoint):
    url = endpoint["url"]
    timeout = endpoint["timeout"]
    expected = endpoint["expected_status"]
    threshold = endpoint["max_response_time"]

    start = time.monotonic()

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "DevOps-API-Monitor/1.0"}
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status

        elapsed = round(time.monotonic() - start, 3)

        if status != expected:
            return {
                "status": "FAIL",
                "failure_type": "UNEXPECTED_STATUS",
                "http_status": status,
                "response_time": elapsed,
                "message": f"Expected HTTP {expected}, got {status}"
            }

        if elapsed > threshold:
            return {
                "status": "FAIL",
                "failure_type": "SLOW_RESPONSE",
                "http_status": status,
                "response_time": elapsed,
                "message": f"Response time {elapsed}s exceeds {threshold}s"
            }

        return {
            "status": "OK",
            "failure_type": None,
            "http_status": status,
            "response_time": elapsed,
            "message": "Endpoint is healthy"
        }

    except urllib.error.HTTPError as exc:
        elapsed = round(time.monotonic() - start, 3)

        if exc.code == expected:
            status = "OK" if elapsed <= threshold else "FAIL"
            return {
                "status": status,
                "failure_type": None if status == "OK" else "SLOW_RESPONSE",
                "http_status": exc.code,
                "response_time": elapsed,
                "message": (
                    "Endpoint returned expected HTTP status"
                    if status == "OK"
                    else f"Response time {elapsed}s exceeds {threshold}s"
                )
            }

        return {
            "status": "FAIL",
            "failure_type": "UNEXPECTED_STATUS",
            "http_status": exc.code,
            "response_time": elapsed,
            "message": f"Expected HTTP {expected}, got {exc.code}"
        }

    except urllib.error.URLError as exc:
        failure_type, message = classify_error(exc.reason)

    except (TimeoutError, socket.timeout, ssl.SSLError, OSError) as exc:
        failure_type, message = classify_error(exc)

    elapsed = round(time.monotonic() - start, 3)

    return {
        "status": "FAIL",
        "failure_type": failure_type,
        "http_status": None,
        "response_time": elapsed,
        "message": message
    }


def validate_config(data):
    if not isinstance(data, dict):
        raise ValueError("Config must be a JSON object")

    endpoints = data.get("endpoints")

    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError("'endpoints' must be a non-empty list")

    for index, endpoint in enumerate(endpoints, start=1):
        if not isinstance(endpoint, dict):
            raise ValueError(f"Endpoint {index} must be an object")

        for field in (
            "name", "url", "expected_status",
            "timeout", "max_response_time"
        ):
            if field not in endpoint:
                raise ValueError(
                    f"Endpoint {index} is missing '{field}'"
                )

        parsed = urlparse(endpoint["url"])

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
        ):
            raise ValueError(
                f"Endpoint {index} has an invalid HTTP URL"
            )

        if (
            type(endpoint["expected_status"]) is not int
            or not 100 <= endpoint["expected_status"] <= 599
        ):
            raise ValueError(
                f"Endpoint {index}: invalid expected_status"
            )

        for field in ("timeout", "max_response_time"):
            value = endpoint[field]
            if (
                type(value) not in (int, float)
                or not 0 < value < float("inf")
            ):
                raise ValueError(
                    f"Endpoint {index}: '{field}' must be positive"
                )

    return endpoints


def write_result(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(result, ensure_ascii=False) + "\n")


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        log("Telegram not configured; notification skipped")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = json.dumps({
        "chat_id": chat_id,
        "text": message
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                log(f"Telegram notification failed: HTTP {response.status}")
                return False

        return True

    except (urllib.error.URLError, OSError) as exc:
        log(f"Telegram notification failed: {type(exc).__name__}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Check API endpoints and classify failures."
    )

    parser.add_argument(
        "--config",
        default="lab-03/config/endpoints.json",
        help="Path to JSON configuration"
    )

    parser.add_argument(
        "--log",
        default="lab-03/api-monitor-results.jsonl",
        help="Path to structured JSONL log"
    )

    args = parser.parse_args()

    try:
        with open(args.config, encoding="utf-8") as file:
            data = json.load(file)

        endpoints = validate_config(data)

    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: Invalid configuration: {exc}", file=sys.stderr)
        return EXIT_CONFIG

    log(f"Checking {len(endpoints)} endpoints")

    failed = 0

    for endpoint in endpoints:
        result = None

        for attempt in range(1, 3):
            result = check_endpoint(endpoint)

            if result["status"] == "OK":
                break

            if result["failure_type"] not in (
                "DNS_ERROR",
                "CONNECTION_REFUSED",
                "TIMEOUT",
                "SSL_ERROR",
                "NETWORK_ERROR"
            ):
                break

            if attempt == 1:
                log(f"Retrying {endpoint['name']} after network error")
                time.sleep(1)

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "name": endpoint["name"],
            "url": endpoint["url"],
            **result
        }

        write_result(Path(args.log), record)

        if result["status"] == "OK":
            log(f"OK: {endpoint['name']} ({result['response_time']}s)")
        else:
            failed += 1
            failure_type = result["failure_type"]

            log(
                f"FAIL: {endpoint['name']} | "
                f"{failure_type} | {result['message']}"
            )

            send_telegram(
                f"API Monitor Alert\n"
                f"Target: {endpoint['name']}\n"
                f"Type: {failure_type}\n"
                f"Details: {result['message']}"
            )

    log(f"Completed: {len(endpoints) - failed} OK, {failed} failed")

    return EXIT_FAILURE if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
