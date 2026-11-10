#!/usr/bin/env bash
# Render the first ```mermaid block of a markdown file to PNG with the local Chrome.
# Uses mermaid's ELK layout engine (orthogonal edge routing), then lifts each lane title
# above the edges and gives it a white backing so crossing lines cannot sit on the text.
set -euo pipefail
SRC="${1:?markdown file}"; OUT="${2:?output png}"; SCALE="${3:-2}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

python3 - "$SRC" "$WORK" <<'PY'
import json, pathlib, sys
src, work = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
defn = src.read_text().split("```mermaid")[1].split("```")[0].strip()
(work/"render.html").write_text("""<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;background:#ffffff}#c{display:inline-block;padding:20px;background:#ffffff}
</style></head><body><div id="c"></div>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
let layout = 'dagre';
try {
  const elk = await import('https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@1/dist/mermaid-layout-elk.esm.min.mjs');
  mermaid.registerLayoutLoaders(elk.default); layout = 'elk';
} catch (e) { /* keep the default engine */ }
mermaid.initialize({startOnLoad:false, theme:'neutral', layout,
                    elk:{nodePlacementStrategy:'NETWORK_SIMPLEX', mergeEdges:false},
                    flowchart:{htmlLabels:true, useMaxWidth:false}});
try {
  const {svg} = await mermaid.render('graph', %s);
  document.getElementById('c').innerHTML = svg;
  const s = document.querySelector('#c svg'); s.removeAttribute('style');

  // Lane titles are drawn before the edges, so any edge entering a lane from above
  // crosses the title. Move each title to the end of the drawing order and lay a white
  // rect under it, so the lines pass behind the words.
  const NS = 'http://www.w3.org/2000/svg';
  const root = s.querySelector('g.root');
  for (const g of [...s.querySelectorAll('g.cluster-label')]) {
    const fo = g.querySelector('foreignObject');
    const m = /translate\\(([-\\d.]+)[, ]+([-\\d.]+)\\)/.exec(g.getAttribute('transform') || '');
    if (!fo || !m) continue;
    const x = parseFloat(m[1]), y = parseFloat(m[2]);
    const w = parseFloat(fo.getAttribute('width')), h = parseFloat(fo.getAttribute('height'));
    const pad = 10;
    const r = document.createElementNS(NS, 'rect');
    r.setAttribute('x', x - pad); r.setAttribute('y', y - 3);
    r.setAttribute('width', w + 2 * pad); r.setAttribute('height', h + 6);
    r.setAttribute('fill', '#ffffff');
    root.appendChild(r); root.appendChild(g);
  }

  // Mermaid draws no crossing markers, so every intersection is an ambiguous X. Give
  // each edge a white halo drawn just before its own stroke: an edge then breaks every
  // edge already drawn, which reads as a jump at each crossing.
  for (const path of [...s.querySelectorAll('g.edgePaths path')]) {
    const halo = path.cloneNode(false);
    halo.removeAttribute('marker-end'); halo.removeAttribute('marker-start');
    halo.removeAttribute('id'); halo.removeAttribute('class');
    const w = parseFloat(getComputedStyle(path).strokeWidth) || 1;
    halo.setAttribute('style', 'fill:none;stroke:#ffffff;stroke-width:' + (w + 5) + 'px;'
      + 'stroke-dasharray:' + (getComputedStyle(path).strokeDasharray || 'none') + ';');
    path.parentNode.insertBefore(halo, path);
  }

  const r = s.getBoundingClientRect();
  document.title = 'READY ' + Math.ceil(r.width) + 'x' + Math.ceil(r.height) + ' ' + layout;
} catch (e) { document.title = 'ERROR ' + e.message; }
</script></body></html>""" % json.dumps(defn))
PY

common=(--headless=new --disable-gpu --no-first-run --hide-scrollbars
        --user-data-dir="$WORK/profile" --virtual-time-budget=30000)
title=$("$CHROME" "${common[@]}" --dump-dom "file://$WORK/render.html" 2>/dev/null \
        | sed -n 's/.*<title>\(.*\)<\/title>.*/\1/p' | head -1)
case "$title" in READY*) ;; *) echo "render failed: ${title:-no title}" >&2; exit 1 ;; esac
dims=$(echo "$title" | awk '{print $2}'); engine=$(echo "$title" | awk '{print $3}')
W=$(( ${dims%x*} + 40 )); H=$(( ${dims#*x} + 40 ))

"$CHROME" "${common[@]}" --force-device-scale-factor="$SCALE" --window-size="$W,$H" \
          --screenshot="$OUT" "file://$WORK/render.html" >/dev/null 2>&1
echo "$OUT  ($(( W * SCALE ))x$(( H * SCALE )) px, $engine layout)"
