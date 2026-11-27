#!/usr/bin/env bash
# Rebuilds the guide PDFs in docs/user-guide/ from docs/USER_GUIDE.md and
# docs/USER_GUIDE_WITH_SAMPLE_DATA.md (release checklist, docs/RELEASE.md).
# Needs pandoc and the frontend's dependencies (npm ci in frontend/; Playwright's Chromium, or
# PW_CHROMIUM pointing at a Chrome binary).
set -euo pipefail
cd "$(dirname "$0")/.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
build() {  # build <guide name> <PDF title>
  local name=$1 title=$2
  # Each "<!-- page -->" marker in a guide starts a new printed page.
  sed 's#<!-- page -->#<div class="pb"></div>#' "docs/$name.md" > "$work/$name.md"
  pandoc "$work/$name.md" -f markdown -t html5 -s --metadata title="$title" --css style.css \
    -o "$work/$name.html"
  # Drop pandoc's own title block: each guide starts with its own title.
  python3 - "$work/$name.html" <<'PY'
import re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
open(p, "w", encoding="utf-8").write(re.sub(r'<header id="title-block-header">.*?</header>', "", s, flags=re.S))
PY
  (cd frontend && node ../tools/user_guide/print.mjs "$work/$name.html" "../docs/user-guide/$name.pdf")
  echo "docs/user-guide/$name.pdf rebuilt from docs/$name.md"
}

cp tools/user_guide/style.css "$work/style.css"
cp -r docs/images "$work/images"
build USER_GUIDE "GovMonitor User Guide"
build USER_GUIDE_WITH_SAMPLE_DATA "GovMonitor User Guide with Sample Data"
