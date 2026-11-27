#!/usr/bin/env bash
# Rebuilds docs/user-guide/USER_GUIDE.pdf from docs/USER_GUIDE.md (release checklist, docs/RELEASE.md).
# Needs pandoc and the frontend's dependencies (npm ci in frontend/; Playwright's Chromium, or
# PW_CHROMIUM pointing at a Chrome binary).
set -euo pipefail
cd "$(dirname "$0")/.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# Each "<!-- page -->" marker in the guide starts a new printed page.
sed 's#<!-- page -->#<div class="pb"></div>#' docs/USER_GUIDE.md > "$work/guide.md"
cp tools/user_guide/style.css "$work/style.css"
cp -r docs/images "$work/images"
pandoc "$work/guide.md" -f markdown -t html5 -s --metadata title="GovMonitor User Guide" \
  --css style.css -o "$work/guide.html"
# Drop pandoc's own title block: the guide starts with its own title.
python3 - "$work/guide.html" <<'PY'
import re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
open(p, "w", encoding="utf-8").write(re.sub(r'<header id="title-block-header">.*?</header>', "", s, flags=re.S))
PY
(cd frontend && node ../tools/user_guide/print.mjs "$work/guide.html" ../docs/user-guide/USER_GUIDE.pdf)
echo "docs/user-guide/USER_GUIDE.pdf rebuilt from docs/USER_GUIDE.md"
