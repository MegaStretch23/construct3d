import csv, io, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from construct3d import cli  # noqa: E402
from construct3d.model import InputError, build_scene, part_bounds, parse_products, rotate_xyz  # noqa: E402
from construct3d.viewer import render_html, script_safe_json  # noqa: E402


def one(**kw):
    p = {"name": "Thing", "width": 10, "depth": 20, "height": 30}
    p.update(kw)
    return build_scene(json.dumps([p]))["items"][0]


class Model(unittest.TestCase):
    def test_box_dims_and_floor(self):
        it = one()
        self.assertEqual(it["dims_cm"], [10, 30, 20])   # x width, y height, z depth
        self.assertEqual(it["bounds"]["min"][1], 0)
        self.assertEqual(it["source"], "preset:box")

    def test_units(self):
        self.assertEqual(build_scene(json.dumps([{"name": "a", "width": 100, "depth": 100, "height": 100}]), unit="mm")["items"][0]["dims_cm"], [10, 10, 10])
        self.assertEqual(build_scene(json.dumps([{"name": "a", "width": 1, "depth": 1, "height": 1}]), unit="in")["items"][0]["dims_cm"], [2.54, 2.54, 2.54])

    def test_keyword_presets(self):
        self.assertEqual(one(name="Blue coffee mug")["source"], "preset:mug")
        self.assertEqual(one(name="Water bottle")["source"], "preset:bottle")
        self.assertEqual(one(name="A4 poster")["source"], "preset:poster")
        self.assertEqual(one(name="Mugwort tea")["source"], "preset:box")      # whole word only
        self.assertEqual(one(name="Candle", shape="sphere")["source"], "preset:ball")  # explicit shape wins

    def test_explicit_parts(self):
        it = one(parts=[{"shape": "sphere", "size": [5], "pos": [100, 50, 0]}, {"shape": "box", "size": [2, 2, 2], "pos": [100, 5, 0]}])
        self.assertEqual(it["source"], "parts")
        self.assertEqual(it["bounds"]["min"][1], 0)                 # dropped onto the floor
        self.assertAlmostEqual((it["bounds"]["min"][0] + it["bounds"]["max"][0]) / 2, 0, places=3)

    def test_bad_input(self):
        for bad in ('[{"name": "x", "width": 0, "depth": 1, "height": 1}]', '[{"name": "x", "width": "abc", "depth": 1, "height": 1}]',
                    '[{"name": "x", "width": 1, "depth": 1}]', '[{"width": 1, "depth": 1, "height": 1}]', '[]', '{"a": 1}', 'not json [',
                    '[{"name": "x", "width": 1e9, "depth": 1, "height": 1}]', '[{"name": "x", "width": NaN, "depth": 1, "height": 1}]',
                    '[{"name": "x", "width": 1, "depth": 1, "height": 1, "color": "red"}]',
                    '[{"name": "x", "width": 1, "depth": 1, "height": 1, "url": "javascript:alert(1)"}]',
                    '[{"name": "x", "parts": [{"shape": "cube", "size": [1]}]}]', '[{"name": "x", "parts": [{"shape": "box", "size": [1, 2]}]}]'):
            with self.assertRaises(InputError, msg=bad):
                build_scene(bad)
        with self.assertRaises(InputError):
            build_scene('[{"name": "x", "width": 1, "depth": 1, "height": 1}]', unit="furlong")

    def test_csv(self):
        text = "name,width,depth,height,color,price\nMug,8,8,9,#112233,$5\nBall,6,6,6,,\n"
        scene = build_scene(text)
        self.assertEqual([i["name"] for i in scene["items"]], ["Mug", "Ball"])
        self.assertEqual(scene["items"][0]["price"], "$5")
        self.assertEqual(parse_products(text)[1]["width"], "6")

    def test_duplicate_names_get_unique_ids(self):
        ids = [i["id"] for i in build_scene(json.dumps([{"name": "A b", "width": 1, "depth": 1, "height": 1}] * 3))["items"]]
        self.assertEqual(len(set(ids)), 3)

    def test_layout_no_overlap(self):
        items = build_scene(json.dumps([{"name": f"p{k}", "width": 10 + k, "depth": 12, "height": 5} for k in range(9)]))["items"]
        boxes = [(i["position"][0] + i["bounds"]["min"][0], i["position"][0] + i["bounds"]["max"][0],
                  i["position"][2] + i["bounds"]["min"][2], i["position"][2] + i["bounds"]["max"][2]) for i in items]
        for a in range(len(boxes)):
            for b in range(a + 1, len(boxes)):
                A, B = boxes[a], boxes[b]
                self.assertTrue(A[1] <= B[0] or B[1] <= A[0] or A[3] <= B[2] or B[3] <= A[2], f"{a} overlaps {b}")

    def test_rotation_matches_known_values(self):
        x, y, z = rotate_xyz((1, 0, 0), (0, 0, 90))
        self.assertAlmostEqual(y, 1); self.assertAlmostEqual(x, 0, places=9)
        x, y, z = rotate_xyz((1, 0, 0), (0, 90, 0))
        self.assertAlmostEqual(z, -1); self.assertAlmostEqual(x, 0, places=9)
        lo, hi = part_bounds({"shape": "box", "size": [2, 4, 6], "pos": [0, 0, 0], "rot": [0, 90, 0]})
        self.assertAlmostEqual(hi[0], 3); self.assertAlmostEqual(hi[2], 1)


class Html(unittest.TestCase):
    def test_script_safe(self):
        self.assertNotIn("<", script_safe_json({"a": "</script><img src=x onerror=1>"}))
        scene = build_scene(json.dumps([{"name": "</script><img src=x onerror=alert(1)>& ", "width": 1, "depth": 1, "height": 1}]), title="<b>t</b></title>")
        page = render_html(scene)
        self.assertEqual(page.lower().count("</script"), 4)   # only the 4 real script tags
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;b&gt;t&lt;/b&gt;", page)

    def test_placeholder_in_title_not_expanded(self):
        page = render_html(build_scene(json.dumps([{"name": "a", "width": 1, "depth": 1, "height": 1}]), title="__THREE__"))
        self.assertLess(len(page), 900_000)

    def test_self_contained(self):
        page = render_html(build_scene(json.dumps(cli.SAMPLE)))
        self.assertNotIn("src=\"http", page); self.assertNotIn("href=\"http", page); self.assertNotIn("<link", page)
        self.assertEqual(page.count("<canvas"), 1)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "construct3d", *args], cwd=ROOT, capture_output=True, text=True)

    def test_selftest(self):
        r = self.run_cli("selftest")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("selftest OK", r.stdout)

    def test_build_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "p.json"; src.write_text(json.dumps(cli.SAMPLE))
            out = Path(td) / "o.html"; js = Path(td) / "o.json"
            r = self.run_cli("build", str(src), "-o", str(out), "--json", str(js))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("6 products", r.stdout)
            self.assertEqual(json.loads(js.read_text())["schema"], "construct3d/1")
            bad = Path(td) / "bad.json"; bad.write_text("[{}]")
            r = self.run_cli("build", str(bad), "-o", str(out))
            self.assertEqual(r.returncode, 1); self.assertIn("name is required", r.stderr)
            r = self.run_cli("build", str(Path(td) / "missing.json"))
            self.assertEqual(r.returncode, 1); self.assertIn("cannot read", r.stderr)
        self.assertEqual(self.run_cli().returncode, 2)

    def test_sample_roundtrip(self):
        r = self.run_cli("sample")
        self.assertEqual(json.loads(r.stdout), cli.SAMPLE)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class Parity(unittest.TestCase):
    """The viewer's own buildScene() run by three.js in Node must give the same world boxes as the Python bounds."""

    def check(self, products):
        scene = build_scene(json.dumps(products))
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "scene.json"; f.write_text(json.dumps(scene))
            r = subprocess.run(["node", "--no-warnings", str(ROOT / "js_tests" / "world_boxes.mjs"), str(f)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout)
        for it in scene["items"]:
            g = got[it["id"]]
            self.assertEqual(g["meshes"], len(it["parts"]))
            for i in range(3):
                self.assertAlmostEqual(g["min"][i], it["position"][i] + it["bounds"]["min"][i], delta=2e-3, msg=f"{it['id']} min[{i}]")
                self.assertAlmostEqual(g["max"][i], it["position"][i] + it["bounds"]["max"][i], delta=2e-3, msg=f"{it['id']} max[{i}]")

    def test_sample_catalog(self):
        self.check(cli.SAMPLE)

    def test_rotated_parts(self):
        self.check([{"name": "rot", "parts": [
            {"shape": "box", "size": [4, 2, 6], "pos": [1, 3, 2], "rot": [30, 45, 60]},
            {"shape": "cylinder", "size": [2, 8], "pos": [-5, 1, 0], "rot": [0, 0, 90]},
            {"shape": "torus", "size": [3, 0.5], "pos": [0, 8, 0], "rot": [90, 0, 0]},
            {"shape": "cone", "size": [2, 5], "pos": [4, 4, 4], "rot": [10, 20, 30]}]}])


if __name__ == "__main__":
    unittest.main()
