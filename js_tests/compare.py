"""Compare the Python bounds in a scene.json with the world boxes three.js computed in Node (world_boxes.mjs)."""
import json, sys
scene = json.load(open(sys.argv[1])); got = json.load(open(sys.argv[2]))
worst = 0.0
for it in scene["items"]:
    g = got[it["id"]]
    d = max(abs(g[k][i] - (it["position"][i] + it["bounds"][k][i])) for k in ("min", "max") for i in range(3))
    worst = max(worst, d)
    print(f"{it['id']:<18} python vs three.js max difference {d:.6f} cm")
print(f"{len(scene['items'])} items, worst difference {worst:.6f} cm")
