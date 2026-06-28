#!/usr/bin/env bash
#
# Deploy the wiki site: copy source static files from wiki/ -> docs/.
# docs/ is what GitHub Pages serves; this script is the "copy" half of the
# manual copy + commit deploy flow. It does NOT commit or push.
#
# Usage:
#   ./deploy.sh            # sync HTML/JS/JSON
#   ./deploy.sh --thumbs   # also copy new thumbnails from output/objects/
#   ./deploy.sh --check    # show what would change, copy nothing (dry run)
#
set -euo pipefail

# Run from the wiki/ dir regardless of where the script is invoked from.
cd "$(dirname "$0")"
SRC="."
DST="../docs"

THUMBS=0
DRY=0
for arg in "$@"; do
  case "$arg" in
    --thumbs) THUMBS=1 ;;
    --check|--dry-run) DRY=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Static files that live in both wiki/ (source) and docs/ (deploy).
FILES=(
  "index.html"
  "viewer.html"
  "catalog.json"
  "ikea.json"
  "js/viewer.js"
)

copy() {  # copy <relative-path>, creating the destination dir as needed
  local rel="$1" from="$SRC/$1" to="$DST/$1"
  if [[ ! -f "$from" ]]; then
    echo "  skip   $rel (missing in source)"
    return
  fi
  if [[ -f "$to" ]] && cmp -s "$from" "$to"; then
    echo "  same   $rel"
    return
  fi
  if [[ "$DRY" == 1 ]]; then
    echo "  CHANGED $rel (would copy)"
    return
  fi
  mkdir -p "$(dirname "$to")"
  cp "$from" "$to"
  echo "  copied $rel"
}

[[ "$DRY" == 1 ]] && label="  (dry run)" || label=""
echo "Deploying wiki/ -> docs/$label"
for f in "${FILES[@]}"; do copy "$f"; done

# Thumbnails are build output (output/ is gitignored); only sync on request,
# and only the ones that exist. New objects are the usual reason to pass --thumbs.
if [[ "$THUMBS" == 1 ]]; then
  echo "Thumbnails:"
  shopt -s nullglob
  count=0
  for dir in "$SRC"/output/objects/*/; do
    name="$(basename "$dir")"
    thumb="$dir/thumb.png"
    [[ -f "$thumb" ]] || continue
    to="$DST/objects/$name/thumb.png"
    if [[ -f "$to" ]] && cmp -s "$thumb" "$to"; then continue; fi
    if [[ "$DRY" == 1 ]]; then
      echo "  CHANGED objects/$name/thumb.png (would copy)"
    else
      mkdir -p "$(dirname "$to")"
      cp "$thumb" "$to"
      echo "  copied objects/$name/thumb.png"
    fi
    count=$((count + 1))
  done
  [[ "$count" == 0 ]] && echo "  (no thumbnail changes)"
fi

echo
echo "Done. Review with:  git -C .. status docs/"
echo "Then commit + push docs/ to publish (GitHub Pages auto-deploys)."
