#!/usr/bin/env bash
# Export docs/<name>.md to docs/<name>.pdf (pandoc → HTML → headless Chrome). Mermaid diagrams are rendered in the page.
#   scripts/export_pdf.sh project-description results
set -euo pipefail
DOCS="$(cd "$(dirname "$0")/../../docs" && pwd)"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/style.html" <<'EOF'
<style>
  @page { size: A4; margin: 16mm 15mm; }
  body { font-family: "PingFang SC", "Noto Serif SC", serif; font-size: 10.5pt; line-height: 1.65; color: #141412; max-width: none; }
  h1 { font-size: 22pt; border-bottom: 2px solid #141412; padding-bottom: 6px; }
  h2 { font-size: 14pt; margin-top: 22px; border-left: 4px solid #e8452c; padding-left: 8px; }
  table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 9pt; page-break-inside: avoid; }
  th, td { border: 1px solid #d9d2c2; padding: 4px 6px; text-align: left; vertical-align: top; }
  th { background: #141412; color: #fbf9f4; }
  code { font-family: "JetBrains Mono", Menlo, monospace; font-size: 8.5pt; background: #f2eee5; padding: 0 3px; }
  pre { background: #f2eee5; padding: 8px 10px; overflow-wrap: anywhere; white-space: pre-wrap; }
  pre.mermaid { background: none; text-align: center; }
  pre.mermaid svg { max-width: 100% !important; max-height: 130mm; height: auto; }
  a { color: #141412; }
</style>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  document.querySelectorAll('pre.mermaid').forEach((pre) => { pre.textContent = pre.textContent; });
  mermaid.initialize({ startOnLoad: false, theme: 'neutral', flowchart: { htmlLabels: true } });
  await mermaid.run({ querySelector: 'pre.mermaid' });
</script>
EOF

for name in "$@"; do
  pandoc "$DOCS/$name.md" -f gfm -t html5 -s --metadata title="$name" -H "$TMP/style.html" -o "$TMP/$name.html"
  # pandoc's standalone template prints the metadata title; the document's own H1 is the title
  sed -i '' '/<header id="title-block-header">/,/<\/header>/d' "$TMP/$name.html"
  # wide left-to-right diagrams shrink to unreadable on A4; lay them out top-to-bottom in print
  sed -i '' 's/flowchart LR/flowchart TB/' "$TMP/$name.html"
  "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --virtual-time-budget=20000 \
    --print-to-pdf="$DOCS/$name.pdf" "file://$TMP/$name.html" >/dev/null 2>&1
  echo "wrote $DOCS/$name.pdf"
done
