#!/usr/bin/env bash

# Стандартні системні шляхи для запуску через cron.
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${MONITOR_CONFIG:-$SCRIPT_DIR/config/monitor.conf}"

if [[ ! -f "$CONFIG_FILE" ]]; then
    printf 'ERROR: Configuration file not found: %s\n' "$CONFIG_FILE" >&2
    exit 2
fi

# Завантаження конфігурації.
# shellcheck source=/dev/null
source "$CONFIG_FILE"

CPU_THRESHOLD="${CPU_THRESHOLD:-90}"
MEMORY_THRESHOLD="${MEMORY_THRESHOLD:-90}"
DISK_FREE_THRESHOLD="${DISK_FREE_THRESHOLD:-10}"
MONITOR_PROCESSES="${MONITOR_PROCESSES:-}"
LOG_FILE="${LOG_FILE:-$HOME/devops-monitor.log}"
DISK_PATH="${DISK_PATH:-$HOME}"

OS="$(uname -s)"
FAILED=0

log_message() {
    local level="$1"
    local metric="$2"
    local value="$3"
    local message="$4"
    local line

    line="$(date '+%Y-%m-%d %H:%M:%S') | $level | $metric | $value | $message"

    printf '%s\n' "$line"

    if [[ "$level" == "WARNING" || "$level" == "ERROR" ]]; then
        if ! printf '%s\n' "$line" >> "$LOG_FILE"; then
            printf 'ERROR: Cannot write to log: %s\n' "$LOG_FILE" >&2
            exit 2
        fi
    fi
}

validate_config() {
    local name value

    for name in CPU_THRESHOLD MEMORY_THRESHOLD DISK_FREE_THRESHOLD; do
        value="${!name}"

        if [[ ! "$value" =~ ^[0-9]+$ ]]; then
            log_message "ERROR" "CONFIG" "$name" "Поріг повинен бути цілим числом"
            exit 2
        fi

        if (( 10#$value > 100 )); then
            log_message "ERROR" "CONFIG" "$name" "Поріг не може перевищувати 100%"
            exit 2
        fi
    done

    CPU_THRESHOLD=$((10#$CPU_THRESHOLD))
    MEMORY_THRESHOLD=$((10#$MEMORY_THRESHOLD))
    DISK_FREE_THRESHOLD=$((10#$DISK_FREE_THRESHOLD))

    if [[ ! -d "$DISK_PATH" ]]; then
        log_message "ERROR" "CONFIG" "$DISK_PATH" "Шлях до диска не існує"
        exit 2
    fi
}

get_cpu_usage() {
    if [[ "$OS" == "Darwin" ]]; then
        top -l 1 -n 0 | awk '/CPU usage:/ {
            for (i = 1; i <= NF; i++) {
                if ($i == "idle") {
                    idle = $(i - 1)
                    gsub(/%/, "", idle)
                    printf "%.0f\n", 100 - idle
                    exit
                }
            }
        }'
    else
        top -bn1 | awk -F',' '/Cpu\(s\)/ {
            for (i = 1; i <= NF; i++) {
                if ($i ~ / id/) {
                    split($i, a, " ")
                    gsub(/,/, ".", a[1])
                    printf "%.0f\n", 100 - a[1]
                    exit
                }
            }
        }'
    fi
}

get_memory_usage() {
    if [[ "$OS" == "Darwin" ]]; then
        local total page_size used_pages

        total="$(sysctl -n hw.memsize)"

        page_size="$(vm_stat | awk -F'page size of ' '
            NR == 1 {
                split($2, a, " ")
                print a[1]
            }
        ')"

        used_pages="$(vm_stat | awk '
            /Pages active:/ {
                active = $3
                gsub(/\./, "", active)
            }
            /Pages wired down:/ {
                wired = $4
                gsub(/\./, "", wired)
            }
            /Pages occupied by compressor:/ {
                compressed = $5
                gsub(/\./, "", compressed)
            }
            END {
                print active + wired + compressed
            }
        ')"

        awk -v pages="$used_pages" \
            -v size="$page_size" \
            -v total="$total" '
            BEGIN {
                if (total <= 0 || size <= 0) {
                    exit 1
                }
                printf "%.0f\n", pages * size / total * 100
            }
        '
    else
        free -b | awk '/^Mem:/ {
            if ($2 <= 0) {
                exit 1
            }
            printf "%.0f\n", ($2 - $7) / $2 * 100
        }'
    fi
}

get_disk_free() {
    df -Pk "$DISK_PATH" | awk 'NR == 2 {
        if ($2 <= 0) {
            exit 1
        }
        printf "%.0f\n", $4 / $2 * 100
    }'
}

validate_metric() {
    local name="$1"
    local value="$2"

    if [[ ! "$value" =~ ^[0-9]+$ ]] || (( value > 100 )); then
        log_message "ERROR" "$name" "N/A" "Не вдалося отримати коректний показник"
        exit 2
    fi
}

check_thresholds() {
    local cpu="$1"
    local memory="$2"
    local disk_free="$3"

    if (( cpu > CPU_THRESHOLD )); then
        log_message "WARNING" "CPU" "${cpu}%" "Перевищено поріг ${CPU_THRESHOLD}%"
        FAILED=1
    else
        log_message "OK" "CPU" "${cpu}%" "Норма"
    fi

    if (( memory > MEMORY_THRESHOLD )); then
        log_message "WARNING" "MEMORY" "${memory}%" "Перевищено поріг ${MEMORY_THRESHOLD}%"
        FAILED=1
    else
        log_message "OK" "MEMORY" "${memory}%" "Норма"
    fi

    if (( disk_free < DISK_FREE_THRESHOLD )); then
        log_message "WARNING" "DISK_FREE" "${disk_free}%" "Менше порога ${DISK_FREE_THRESHOLD}%"
        FAILED=1
    else
        log_message "OK" "DISK_FREE" "${disk_free}%" "Норма"
    fi
}

check_processes() {
    local process

    for process in $MONITOR_PROCESSES; do
        if pgrep -x "$process" >/dev/null 2>&1; then
            log_message "OK" "PROCESS" "$process" "Процес працює"
        else
            log_message "WARNING" "PROCESS" "$process" "Процес не знайдено"
            FAILED=1
        fi
    done
}

main() {
    local cpu memory disk_free

    if [[ "$OS" != "Darwin" && "$OS" != "Linux" ]]; then
        log_message "ERROR" "SYSTEM" "$OS" "Операційна система не підтримується"
        exit 2
    fi

    validate_config

    if ! cpu="$(get_cpu_usage)"; then
        log_message "ERROR" "CPU" "N/A" "Помилка отримання завантаження процесора"
        exit 2
    fi

    if ! memory="$(get_memory_usage)"; then
        log_message "ERROR" "MEMORY" "N/A" "Помилка отримання використання пам'яті"
        exit 2
    fi

    if ! disk_free="$(get_disk_free)"; then
        log_message "ERROR" "DISK_FREE" "N/A" "Помилка перевірки диска"
        exit 2
    fi

    validate_metric "CPU" "$cpu"
    validate_metric "MEMORY" "$memory"
    validate_metric "DISK_FREE" "$disk_free"

    check_thresholds "$cpu" "$memory" "$disk_free"
    check_processes

    if (( FAILED != 0 )); then
        exit 1
    fi

    exit 0
}

main "$@"
