#!/usr/bin/env bash
# Refresh the local STMicroelectronics repo catalog.
# Used by Claude / ref-st-github-map.md as a baseline cache so that repo
# lookups don't require a network call every time.
#
# Output: cache/st-repos.json  (JSON array of {name, description, pushedAt})
#
# ST has ~750+ public repos; --limit 1000 captures all current.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="$REPO_ROOT/cache"
OUT="$CACHE_DIR/st-repos.json"

mkdir -p "$CACHE_DIR"

if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: 'gh' (GitHub CLI) is required. Install: https://cli.github.com/" >&2
    exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
    echo "ERROR: 'gh' is not authenticated. Run: gh auth login" >&2
    exit 1
fi

echo "Fetching STMicroelectronics repo catalog..."
gh repo list STMicroelectronics --limit 1000 \
    --json name,description,pushedAt,primaryLanguage \
    > "$OUT.tmp"

count=$(jq -r '. | length' "$OUT.tmp")
mv "$OUT.tmp" "$OUT"
echo "OK: $count repos → $OUT"

# Quick category summary
echo ""
echo "Family HAL drivers (stm32*xx-hal-driver):"
jq -r '.[] | select(.name|test("stm32[a-z0-9]+xx-hal-driver")) | "  \(.name)"' "$OUT" | sort

echo ""
echo "Family Cube packages (STM32Cube*):"
jq -r '.[] | select(.name|test("^STM32Cube[A-Z0-9]+$")) | "  \(.name)"' "$OUT" | sort

echo ""
echo "X-CUBE expansion packs:"
jq -r '.[] | select(.name|test("^x-cube-")) | "  \(.name)"' "$OUT" | sort | head -20
echo "  (and more — see $OUT)"
