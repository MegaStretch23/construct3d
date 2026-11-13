// usage: node js_tests/world_boxes.mjs scene.json  -> JSON {id: {min, max}} computed by three.js from the viewer's own buildScene()
import fs from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..", "construct3d");
const THREE = await import(pathToFileURL(path.join(root, "vendor", "three.module.min.js")));
const core = await import(pathToFileURL(path.join(root, "viewer", "core.js")));
const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const built = core.buildScene(THREE, data);
const out = {};
for (const e of built.entries) out[e.item.id] = { min: e.world.min.toArray(), max: e.world.max.toArray(), meshes: e.meshes.length };
console.log(JSON.stringify(out));
