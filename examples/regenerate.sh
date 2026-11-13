#!/bin/sh
# Rebuilds every file in examples/ from the code in this repo (run from the repo root).
set -e
PY=${PY:-python}
$PY -m construct3d sample > examples/products.json
printf 'name,width,depth,height,category,color,price\nTea tin,7,7,11,kitchen,#8e44ad,$9.00\nSticker sheet,15,0.5,21,paper,#16a085,$4.00\nPhone stand,9,8,12,desk,#2c3e50,$12.00\n' > examples/products.csv
$PY -m construct3d inspect examples/products.json > examples/inspect.txt
$PY -m construct3d build examples/products.json -o examples/catalog.html --json examples/scene.json > examples/build.txt
rm examples/catalog.html   # 690 KB, rebuilt on demand; the saved run is build.txt + scene.json
$PY -m construct3d inspect examples/products.csv > examples/inspect-csv.txt
node --no-warnings js_tests/world_boxes.mjs examples/scene.json > examples/three-world-boxes.json
$PY js_tests/compare.py examples/scene.json examples/three-world-boxes.json > examples/parity.txt
