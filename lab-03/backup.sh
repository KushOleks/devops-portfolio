#!/usr/bin/env bash
set -euo pipefail

SOURCE=""
DEST=""
KEEP=5
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage:
  backup.sh --source PATH --dest PATH [--keep N] [--dry-run]
  backup.sh --help

Options:
  --source PATH   Source directory (required)
  --dest PATH     Backup destination (required)
  --keep N        Number of backups to keep (default: 5)
  --dry-run       Show actions without changing files
  --help          Show this help message

Example:
  ./backup.sh --source "./my project" --dest "./backups" --keep 3
EOF
}

error() {
  local message="$1"
  local code="${2:-1}"
  printf 'ERROR: %s\n' "$message" >&2
  exit "$code"
}

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source|--dest|--keep)
      [[ $# -ge 2 ]] || error "Missing value for $1" 2

      case "$1" in
        --source) SOURCE="$2" ;;
        --dest) DEST="$2" ;;
        --keep) KEEP="$2" ;;
      esac
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      error "Unknown argument: $1. Use --help." 2
      ;;
  esac
done

[[ -n "$SOURCE" ]] || error "--source is required" 2
[[ -n "$DEST" ]] || error "--dest is required" 2
[[ "$KEEP" =~ ^[1-9][0-9]*$ ]] ||
  error "--keep must be a positive integer" 2

[[ -d "$SOURCE" && -r "$SOURCE" && -x "$SOURCE" ]] ||
  error "Source directory does not exist or is not accessible: $SOURCE" 3

SOURCE="$(cd "$SOURCE" && pwd -P)"

# Resolve destination without creating it.
if [[ -d "$DEST" ]]; then
  DEST="$(cd "$DEST" && pwd -P)"
else
  case "$DEST" in
    /*) ;;
    *) DEST="$PWD/$DEST" ;;
  esac
fi

# Prevent recursive backups.
case "$DEST/" in
  "$SOURCE/"*)
    error "Destination must be outside source directory" 2
    ;;
esac

NAME="$(basename "$SOURCE")"
PARENT="$(dirname "$SOURCE")"

# Filename includes timestamp and unique process ID.
STAMP="$(date '+%Y-%m-%d-%H%M%S')"
ARCHIVE="$DEST/$NAME-$STAMP-$$.tar.gz"

log "Source: $SOURCE"
log "Destination: $DEST"
log "Keep: $KEEP"

# Find existing archives belonging to this source.
ARCHIVES=()

if [[ -d "$DEST" ]]; then
  while IFS= read -r -d '' file; do
    ARCHIVES+=("$file")
  done < <(
    find "$DEST" -maxdepth 1 -type f \
      -name "$NAME-????-??-??-??????-*.tar.gz" -print0
  )
fi

# Include the archive that will be created.
ARCHIVES+=("$ARCHIVE")

# Sort archives by name, newest first.
# This works with the default Bash on macOS.
SORTED=()

while IFS= read -r file; do
  SORTED+=("$file")
done < <(
  printf '%s\n' "${ARCHIVES[@]}" | LC_ALL=C sort -r
)

DELETED=0

if [[ "$DRY_RUN" == true ]]; then
  log "DRY RUN: would create $ARCHIVE"
else
  mkdir -p "$DEST"

  [[ -w "$DEST" ]] ||
    error "Destination is not writable: $DEST" 4

  tar -czf "$ARCHIVE" -C "$PARENT" "$NAME" ||
    error "Failed to create archive" 4

  SIZE="$(wc -c < "$ARCHIVE" | tr -d ' ')"
  log "Created: $ARCHIVE ($SIZE bytes)"
fi

# Delete old backups exceeding the retention limit.
for ((i=KEEP; i<${#SORTED[@]}; i++)); do
  file="${SORTED[$i]}"

  if [[ "$DRY_RUN" == true ]]; then
    log "DRY RUN: would delete $file"
  else
    rm -- "$file"
    log "Deleted: $file"
  fi

  DELETED=$((DELETED + 1))
done

if [[ "$DRY_RUN" == true ]]; then
  log "Result: archived=0, deleted=0, planned_deletions=$DELETED, dry_run=true"
else
  log "Result: archived=1, deleted=$DELETED, size=$SIZE bytes"
fi
