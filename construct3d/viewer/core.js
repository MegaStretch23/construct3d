// construct3d viewer core. No imports: three.js is passed in, so Node can run buildScene() for tests.
export function makeGeometry(THREE, p) {
  const s = p.size;
  switch (p.shape) {
    case "box": return new THREE.BoxGeometry(s[0], s[1], s[2]);
    case "cylinder": return new THREE.CylinderGeometry(s[0], s[0], s[1], 32);
    case "cone": return new THREE.ConeGeometry(s[0], s[1], 32);
    case "sphere": return new THREE.SphereGeometry(s[0], 32, 16);
    case "torus": return new THREE.TorusGeometry(s[0], s[1], 16, 48);
  }
  throw new Error("unknown shape " + p.shape);
}

// Builds the scene graph (no renderer, no DOM). Returns {root, entries:[{item, group, meshes, world:Box3}]}.
export function buildScene(THREE, data) {
  const root = new THREE.Group();
  const entries = [];
  for (const item of data.items) {
    const group = new THREE.Group();
    group.name = item.id;
    group.position.set(item.position[0], item.position[1], item.position[2]);
    const meshes = [];
    const c = [0, 1, 2].map(i => (item.bounds.min[i] + item.bounds.max[i]) / 2);
    for (const p of item.parts) {
      const mesh = new THREE.Mesh(makeGeometry(THREE, p), new THREE.MeshStandardMaterial({ color: p.color, roughness: 0.6, metalness: 0.1 }));
      mesh.position.set(p.pos[0], p.pos[1], p.pos[2]);
      if (p.rot) mesh.rotation.set(p.rot[0] * Math.PI / 180, p.rot[1] * Math.PI / 180, p.rot[2] * Math.PI / 180, "XYZ");
      mesh.userData.base = mesh.position.clone();
      mesh.userData.out = new THREE.Vector3(p.pos[0] - c[0], p.pos[1] - c[1], p.pos[2] - c[2]);
      mesh.userData.item = item.id;
      group.add(mesh);
      meshes.push(mesh);
    }
    root.add(group);
    entries.push({ item, group, meshes });
  }
  root.updateMatrixWorld(true);
  for (const e of entries) e.world = new THREE.Box3().setFromObject(e.group);
  return { root, entries };
}

export function start(THREE, data, doc) {
  const $ = id => doc.getElementById(id);
  const canvas = $("c");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x14181f);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 1.1));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(200, 400, 250);
  scene.add(sun);
  const built = buildScene(THREE, data);
  scene.add(built.root);
  const wmin = data.stats.world_min, wmax = data.stats.world_max;
  const ctr = new THREE.Vector3((wmin[0] + wmax[0]) / 2, (wmin[1] + wmax[1]) / 2, (wmin[2] + wmax[2]) / 2);
  const span = Math.max(wmax[0] - wmin[0], wmax[1] - wmin[1], wmax[2] - wmin[2], 10);
  const grid = new THREE.GridHelper(span * 2, 20, 0x556070, 0x2a3140);
  scene.add(grid);
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, span * 40);
  const view = { target: ctr.clone(), dist: span * 1.25, yaw: 0.2, pitch: 0.8 };
  function place() {
    const cp = Math.cos(view.pitch), sp = Math.sin(view.pitch);
    camera.position.set(view.target.x + view.dist * cp * Math.sin(view.yaw), view.target.y + view.dist * sp, view.target.z + view.dist * cp * Math.cos(view.yaw));
    camera.lookAt(view.target);
  }
  let selected = null, explode = 0;
  const emissive = new THREE.Color(0x335577);
  function setSelected(entry) {
    if (selected) for (const m of selected.meshes) m.material.emissive.set(0x000000);
    selected = entry;
    const info = $("info");
    info.textContent = "";
    if (!entry) { info.textContent = "Click a product or pick one from the list."; return; }
    for (const m of entry.meshes) m.material.emissive.copy(emissive);
    const it = entry.item;
    const add = (tag, text) => { const e = doc.createElement(tag); e.textContent = text; info.appendChild(e); return e; };
    add("h2", it.name);
    add("p", `${it.dims_cm[0]} x ${it.dims_cm[2]} x ${it.dims_cm[1]} cm (W x D x H), ${it.parts.length} part${it.parts.length === 1 ? "" : "s"}` + (it.price ? `, ${it.price}` : ""));
    add("p", "Built from: " + it.source);
    if (it.parts.length) add("p", it.parts.map(p => p.name).join(", "));
    if (it.url && /^https?:\/\//i.test(it.url)) { const a = add("a", it.url); a.href = it.url; a.target = "_blank"; a.rel = "noopener noreferrer"; }
    for (const li of doc.querySelectorAll("#list li")) li.classList.toggle("on", li.dataset.id === it.id);
  }
  const list = $("list");
  for (const e of built.entries) {
    const li = doc.createElement("li");
    li.textContent = e.item.name;
    li.dataset.id = e.item.id;
    li.onclick = () => {
      setSelected(e);
      const p = e.world.getCenter(new THREE.Vector3());
      view.target.copy(p);
      view.dist = Math.max(e.world.getSize(new THREE.Vector3()).length() * 2.2, 5);
    };
    list.appendChild(li);
  }
  $("explode").oninput = ev => {
    explode = Number(ev.target.value) / 100;
    for (const e of built.entries) for (const m of e.meshes) m.position.copy(m.userData.base).addScaledVector(m.userData.out, explode * 1.5);
  };
  $("wire").onchange = ev => { for (const e of built.entries) for (const m of e.meshes) m.material.wireframe = ev.target.checked; };
  $("reset").onclick = () => { view.target.copy(ctr); view.dist = span * 1.25; view.yaw = 0.2; view.pitch = 0.8; setSelected(null); };
  // orbit: drag = rotate, shift-drag or right-drag = pan, wheel = zoom, click = select
  let drag = null;
  canvas.addEventListener("contextmenu", ev => ev.preventDefault());
  canvas.addEventListener("pointerdown", ev => { canvas.setPointerCapture(ev.pointerId); drag = { x: ev.clientX, y: ev.clientY, sx: ev.clientX, sy: ev.clientY, pan: ev.shiftKey || ev.button === 2 }; });
  canvas.addEventListener("pointermove", ev => {
    if (!drag) return;
    const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
    drag.x = ev.clientX; drag.y = ev.clientY;
    if (drag.pan) {
      const k = view.dist * 0.0016, right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0), up = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
      view.target.addScaledVector(right, -dx * k).addScaledVector(up, dy * k);
    } else {
      view.yaw -= dx * 0.008;
      view.pitch = Math.max(-1.45, Math.min(1.45, view.pitch + dy * 0.008));
    }
  });
  canvas.addEventListener("pointerup", ev => {
    const moved = drag && Math.hypot(ev.clientX - drag.sx, ev.clientY - drag.sy) > 4;
    drag = null;
    if (moved) return;
    const r = canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(built.entries.flatMap(e => e.meshes), false)[0];
    setSelected(hit ? built.entries.find(e => e.item.id === hit.object.userData.item) : null);
  });
  canvas.addEventListener("wheel", ev => { ev.preventDefault(); view.dist = Math.max(2, Math.min(span * 20, view.dist * Math.exp(ev.deltaY * 0.001))); }, { passive: false });
  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.floor(w * renderer.getPixelRatio()) || canvas.height !== Math.floor(h * renderer.getPixelRatio())) renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }
  setSelected(null);
  (function frame() { resize(); place(); renderer.render(scene, camera); requestAnimationFrame(frame); })();
  return { built, view, setSelected };
}
