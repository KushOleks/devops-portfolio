#!/bin/bash

set -e

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <owner/repository>"
  exit 1
fi

REPOSITORY="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/ruleset.json"

echo "Applying repository rules to $REPOSITORY..."

gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  "repos/$REPOSITORY/rulesets" \
  --input "$CONFIG_FILE"

echo
echo "Ruleset successfully applied to $REPOSITORY."
