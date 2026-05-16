#!/usr/bin/env bash
# Add a standardized "trust + GitHub-first" header to every ref-*.md file.
# Idempotent: detects an existing header by sentinel marker and skips.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

SENTINEL='<!-- @trust-header v1 -->'

# Write header to temp file (heredoc inside $() confuses bash parser due to
# apostrophes in the text).
HEADER_FILE=$(mktemp)
trap 'rm -f "$HEADER_FILE"' EXIT

cat > "$HEADER_FILE" <<'TRUST_HEADER_EOF'
<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).
TRUST_HEADER_EOF

inserted=0
skipped=0
for f in ref-*.md; do
    case "$f" in
        ref-bootloader.md|ref-st-github-map.md) skipped=$((skipped+1)); continue ;;
    esac

    if grep -q "$SENTINEL" "$f" 2>/dev/null; then
        skipped=$((skipped+1))
        continue
    fi

    awk -v hdr_file="$HEADER_FILE" '
        BEGIN {
            while ((getline line < hdr_file) > 0) {
                hdr = hdr (hdr ? "\n" : "") line
            }
            close(hdr_file)
            inserted = 0
        }
        /^# / && !inserted {
            print
            print ""
            print hdr
            print ""
            inserted = 1
            next
        }
        { print }
    ' "$f" > "$f.tmp"

    if grep -q "$SENTINEL" "$f.tmp"; then
        mv "$f.tmp" "$f"
        inserted=$((inserted+1))
        echo "[OK] $f"
    else
        rm "$f.tmp"
        echo "[SKIP - no H1 found] $f"
        skipped=$((skipped+1))
    fi
done

echo ""
echo "Inserted: $inserted   Skipped: $skipped"
