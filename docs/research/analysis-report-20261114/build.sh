#!/usr/bin/env bash
set -euo pipefail
report_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$report_dir"

export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/routeevo-report-uv-cache}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${TMPDIR:-/tmp}/routeevo-matplotlib}"
python3 scripts/verify_sources.py
uv run --with matplotlib==3.10.8 python scripts/analyze.py
python3 ../mac-exploratory-20261114/audit_results.py
uv run --with matplotlib==3.10.8 python scripts/analyze_mac.py --source-commit 5962203315dc1c229cd6ef3255d06e2dc5745436
mkdir -p output/pdf
for pass in 1 2; do
  if ! xelatex -interaction=nonstopmode -halt-on-error \
    -output-directory=output/pdf -jobname=quotacrux-research-report report.tex \
    > output/pdf/build-console.log 2>&1; then
    tail -60 output/pdf/build-console.log
    exit 1
  fi
done
python3 - <<'PY'
import pathlib
import re
log = pathlib.Path('output/pdf/quotacrux-research-report.log').read_text()
problems = re.findall(r'^.*(?:Overfull|Missing character|undefined references|LaTeX Warning|Package .+ Warning).*$' , log, re.M)
if problems:
    raise SystemExit('\n'.join(problems))
print(re.search(r'Output written on .*?\(\d+ pages\)', log, re.S).group(0))
PY
