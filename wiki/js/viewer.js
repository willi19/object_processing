const HF_BASE = 'https://huggingface.co/datasets/willi19/object_processing/resolve/main/';

// Pipeline stages the viewer can toggle between. `file` is relative to the
// object dir on HuggingFace; `simplified` falls back to the legacy mesh.glb.
const STAGES = [
  { id: 'raw',        label: 'Raw',        file: 'stages/raw.glb' },
  { id: 'coacd',      label: 'CoACD',      file: 'stages/coacd.glb' },
  { id: 'simplified', label: 'Simplified', file: 'stages/simplified.glb', fallback: 'mesh.glb' },
];

const AXIS_COLORS = [
  new BABYLON.Color3(1.0, 0.82, 0.10),  // primary symmetry axis
  new BABYLON.Color3(0.20, 0.85, 0.40),
  new BABYLON.Color3(0.36, 0.62, 0.95),
];

(async function () {
  const params = new URLSearchParams(window.location.search);
  const objectId = params.get('id');
  if (!objectId) { showError('No object ID specified.'); return; }

  // Stage GLBs normally load from HuggingFace. ?local=1 loads them from
  // objects/{id}/stages/ under this site instead, for testing before upload.
  const useLocal = params.get('local') === '1';
  const assetBase = (useLocal ? '' : HF_BASE) + 'objects/' + objectId + '/';

  let catalog;
  try {
    catalog = await (await fetch('catalog.json')).json();
  } catch (e) { showError('Failed to load catalog.'); return; }

  const obj = catalog.objects.find(o => o.id === objectId);
  if (!obj) { showError(`Object "${objectId}" not found in catalog.`); return; }

  document.getElementById('obj-label').textContent = obj.label;
  document.title = `${obj.label} - Object Viewer`;
  if (obj.category) {
    const catEl = document.getElementById('obj-category');
    catEl.textContent = obj.category;
    catEl.style.display = '';
  }

  // Optional IKEA purchase link (separate file, merged client-side).
  try {
    const ikea = (await (await fetch('ikea.json')).json()).objects || {};
    const k = ikea[objectId];
    if (k && k.link) {
      const buy = document.getElementById('buy-link');
      buy.href = k.link;
      buy.title = `${k.name} — ${k.description}`;
      buy.style.display = '';
    }
  } catch (e) { /* no purchase link for this object */ }

  // Overlay metadata (OBB / symmetry / tabletop), served locally. Optional.
  let info = null;
  try {
    info = await (await fetch(`objects/${objectId}/info.json`)).json();
  } catch (e) { /* overlays simply stay disabled */ }

  // ── Babylon scene ──────────────────────────────────────────────────────────
  const canvas = document.getElementById('renderCanvas');
  const engine = new BABYLON.Engine(canvas, true, { preserveDrawingBuffer: true, stencil: true });
  const scene = new BABYLON.Scene(engine);
  scene.clearColor = new BABYLON.Color4(0.051, 0.067, 0.09, 1);
  // glTF and our overlay data are both right-handed (object frame). Keep the
  // scene right-handed so the glTF __root__ is identity and overlays built in
  // object-frame coordinates line up with the mesh without conversion.
  scene.useRightHandedSystem = true;

  const camera = new BABYLON.ArcRotateCamera('cam', Math.PI / 4, Math.PI / 3, 2, BABYLON.Vector3.Zero(), scene);
  camera.attachControl(canvas, true);
  camera.wheelPrecision = 50;
  camera.minZ = 0.001;
  camera.lowerRadiusLimit = 0.05;
  camera.upperRadiusLimit = 50;
  camera.angularSensibilityX = 3000;
  camera.angularSensibilityY = 3000;
  camera.panningSensibility = 3000;
  camera.lowerBetaLimit = null;
  camera.upperBetaLimit = null;

  new BABYLON.HemisphericLight('hemi', new BABYLON.Vector3(0, 1, 0), scene).intensity = 0.85;
  const dir = new BABYLON.DirectionalLight('dir', new BABYLON.Vector3(-1, -2, 1), scene);
  dir.intensity = 0.55;

  // State shared across stage loads.
  let currentContainer = null;
  let currentRoot = null;          // glTF __root__ node; overlays parent here
  let standWrap = null;            // wraps currentRoot with the standing pose
  let floorMesh = null;            // ground plane under the standing object
  let overlays = { obb: null, symmetry: null, tabletop: null };
  const shown = { obb: false, symmetry: false, tabletop: false };

  function disposeOverlays() {
    for (const k of Object.keys(overlays)) {
      if (overlays[k]) { overlays[k].dispose(); overlays[k] = null; }
    }
  }

  async function loadStage(stage) {
    document.getElementById('loading').style.display = '';
    document.getElementById('error').style.display = 'none';
    disposeOverlays();
    if (standWrap) { standWrap.dispose(); standWrap = null; }
    if (floorMesh) { floorMesh.dispose(); floorMesh = null; }
    if (currentContainer) { currentContainer.dispose(); currentContainer = null; }

    let file = stage.file;
    try {
      currentContainer = await BABYLON.SceneLoader.LoadAssetContainerAsync(assetBase, file, scene);
    } catch (e) {
      if (stage.fallback) {
        file = stage.fallback;
        currentContainer = await BABYLON.SceneLoader.LoadAssetContainerAsync(assetBase, file, scene);
      } else { throw e; }
    }
    currentContainer.addAllToScene();
    currentRoot = scene.getTransformNodeByName('__root__')
      || currentContainer.transformNodes.find(n => n.name === '__root__')
      || currentContainer.meshes.find(m => m.name === '__root__');

    applyStandingPose();   // rotate the object upright onto the floor
    rebuildFloor();
    fitCamera(currentContainer);
    rebuildOverlays();
    document.getElementById('download-link').href = assetBase + file;
    document.getElementById('download-link').style.display = '';
    document.getElementById('loading').style.display = 'none';
  }

  function fitCamera(container) {
    const meshes = container.meshes.filter(m => m.getTotalVertices() > 0);
    if (!meshes.length) return;
    let min = new BABYLON.Vector3(Infinity, Infinity, Infinity);
    let max = new BABYLON.Vector3(-Infinity, -Infinity, -Infinity);
    meshes.forEach(m => {
      m.computeWorldMatrix(true);
      const b = m.getBoundingInfo().boundingBox;
      min = BABYLON.Vector3.Minimize(min, b.minimumWorld);
      max = BABYLON.Vector3.Maximize(max, b.maximumWorld);
    });
    camera.target = BABYLON.Vector3.Center(min, max);
    camera.radius = max.subtract(min).length() * 1.4;
  }

  // ── Overlays (built in object frame, parented to __root__) ─────────────────
  // Row-major 4x4 (numpy) -> Babylon Matrix (column-major) is a transpose.
  function mat4(rows) {
    return BABYLON.Matrix.FromArray([
      rows[0][0], rows[1][0], rows[2][0], rows[3][0],
      rows[0][1], rows[1][1], rows[2][1], rows[3][1],
      rows[0][2], rows[1][2], rows[2][2], rows[3][2],
      rows[0][3], rows[1][3], rows[2][3], rows[3][3],
    ]);
  }

  // The most upright stable pose = the one giving the tallest footprint
  // (largest z-extent of the OBB after the resting transform). Returns a Babylon
  // Matrix (object -> table) or null.
  function standingPose() {
    if (!info || !info.tabletop_poses || !info.tabletop_poses.length || !info.obb) return null;
    const e = info.obb.extents, T = mat4(info.obb.transform);
    const hx = e[0] / 2, hy = e[1] / 2, hz = e[2] / 2;
    const local = [
      [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
      [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
    ].map(p => new BABYLON.Vector3(p[0], p[1], p[2]));
    let best = null, bestH = -Infinity;
    info.tabletop_poses.forEach(pose => {
      const P = mat4(pose);
      let mn = Infinity, mx = -Infinity;
      local.forEach(c => {
        const w = BABYLON.Vector3.TransformCoordinates(BABYLON.Vector3.TransformCoordinates(c, T), P);
        mn = Math.min(mn, w.z); mx = Math.max(mx, w.z);
      });
      const h = mx - mn;
      if (h > bestH) { bestH = h; best = P; }
    });
    return best;
  }

  // Set a node's local transform from a Babylon Matrix.
  function setNodeMatrix(node, M) {
    const s = new BABYLON.Vector3(), q = new BABYLON.Quaternion(), t = new BABYLON.Vector3();
    M.decompose(s, q, t);
    node.scaling = s; node.rotationQuaternion = q; node.position = t;
  }

  // Rotate the loaded object into its standing pose by wrapping __root__ (so the
  // container's template stays identity — pose instances aren't double-rotated).
  function applyStandingPose() {
    const S = standingPose();
    if (!S || !currentRoot) return;
    standWrap = new BABYLON.TransformNode('stand', scene);
    setNodeMatrix(standWrap, S);
    currentRoot.parent = standWrap;
  }

  function makeFloorSlab(name, size) {
    const m = BABYLON.MeshBuilder.CreateBox(name, { width: size, height: size, depth: 0.002 }, scene);
    m.position.z = -0.001;
    const mat = new BABYLON.StandardMaterial(name + '_mat', scene);
    mat.diffuseColor = new BABYLON.Color3(0.5, 0.5, 0.55);
    mat.alpha = 0.25;
    mat.backFaceCulling = false;
    m.material = mat;
    return m;
  }

  // Ground plane under the single standing object.
  function rebuildFloor() {
    if (floorMesh) { floorMesh.dispose(); floorMesh = null; }
    const e = info && info.obb ? info.obb.extents : [0.1, 0.1, 0.1];
    floorMesh = makeFloorSlab('floor', Math.max(...e) * 4);
  }

  function buildOBB() {
    if (!info || !info.obb) return null;
    const e = info.obb.extents, T = mat4(info.obb.transform);
    const hx = e[0] / 2, hy = e[1] / 2, hz = e[2] / 2;
    const c = [
      [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
      [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
    ].map(p => BABYLON.Vector3.TransformCoordinates(new BABYLON.Vector3(p[0], p[1], p[2]), T));
    const E = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
    const lines = E.map(([a, b]) => [c[a], c[b]]);
    const m = BABYLON.MeshBuilder.CreateLineSystem('obb', { lines }, scene);
    m.color = new BABYLON.Color3(0.27, 0.51, 1.0);
    return m;
  }

  function buildSymmetry() {
    if (!info || !info.symmetry || !info.symmetry.axes.length) return null;
    const ctr = new BABYLON.Vector3(...info.symmetry.center);
    const L = info.symmetry.scale * 0.6;
    const group = new BABYLON.TransformNode('symmetry', scene);
    info.symmetry.axes.forEach((a, i) => {
      const d = new BABYLON.Vector3(...a.axis);
      const p0 = ctr.subtract(d.scale(L)), p1 = ctr.add(d.scale(L));
      const ln = BABYLON.MeshBuilder.CreateLines('sym' + i, { points: [p0, p1] }, scene);
      ln.color = AXIS_COLORS[i % AXIS_COLORS.length];
      ln.parent = group;
    });
    return group;
  }

  // Tabletop poses: instance the object MESH resting in each stable pose, laid
  // out on a grid over a shared floor at table level (z = 0). Each pose matrix
  // (object -> table) plus a grid offset goes straight onto an instance root.
  function buildTabletop() {
    if (!info || !info.tabletop_poses || !info.tabletop_poses.length || !currentContainer) return null;
    const e = info.obb ? info.obb.extents : [0.1, 0.1, 0.1];
    const n = info.tabletop_poses.length;
    const cols = Math.ceil(Math.sqrt(n));
    const spacing = Math.max(...e) * 1.8;
    const group = new BABYLON.TransformNode('tabletop', scene);

    info.tabletop_poses.forEach((pose, k) => {
      const dx = ((k % cols) - (cols - 1) / 2) * spacing;
      const dy = (Math.floor(k / cols) - (cols - 1) / 2) * spacing;
      const M = mat4(pose).multiply(BABYLON.Matrix.Translation(dx, dy, 0));
      // Clone the loaded model (materials shared) and drop it at the pose. The
      // container template is identity, so the standing-pose wrapper is NOT
      // inherited here — instances get exactly the resting pose.
      const inst = currentContainer.instantiateModelsToScene(
        name => `tt${k}_${name}`, false, { doNotInstantiate: true });
      inst.rootNodes.forEach(rn => { setNodeMatrix(rn, M); rn.parent = group; });
    });

    const half = (cols * spacing) / 2 + Math.max(...e);
    makeFloorSlab('tt_floor', half * 2).parent = group;
    return group;
  }

  function rebuildOverlays() {
    disposeOverlays();
    if (shown.obb) overlays.obb = buildOBB();
    if (shown.symmetry) overlays.symmetry = buildSymmetry();
    if (shown.tabletop) overlays.tabletop = buildTabletop();
    // OBB and symmetry live in object frame -> parent to glTF root so they align
    // with the (standing) object. The pose grid is world-frame, left at scene root.
    for (const k of ['obb', 'symmetry']) {
      if (overlays[k] && currentRoot) overlays[k].parent = currentRoot;
    }
    // While showing all poses, hide the single standing object + its floor.
    const single = !shown.tabletop;
    if (standWrap) standWrap.setEnabled(single);
    else if (currentRoot) currentRoot.setEnabled(single);
    if (floorMesh) floorMesh.setEnabled(single);
  }

  function toggleOverlay(kind, on) {
    shown[kind] = on;
    rebuildOverlays();
  }

  // ── Controls ───────────────────────────────────────────────────────────────
  buildControls(STAGES, info, loadStage, toggleOverlay);

  try {
    await loadStage(STAGES[2]);  // default: simplified
  } catch (e) {
    console.error(e);
    showError(`Failed to load 3D model: ${e.message || e}`);
  }

  engine.runRenderLoop(() => scene.render());
  window.addEventListener('resize', () => engine.resize());
})();

function buildControls(stages, info, onStage, onOverlay) {
  const panel = document.getElementById('controls');
  if (!panel) return;

  const stageWrap = document.createElement('div');
  stageWrap.className = 'ctl-group';
  stageWrap.innerHTML = '<div class="ctl-title">Stage</div>';
  stages.forEach((s, i) => {
    const id = 'stage-' + s.id;
    const lab = document.createElement('label');
    lab.className = 'ctl-radio';
    lab.innerHTML = `<input type="radio" name="stage" id="${id}" ${i === 2 ? 'checked' : ''}> ${s.label}`;
    lab.querySelector('input').addEventListener('change', () => onStage(s));
    stageWrap.appendChild(lab);
  });
  panel.appendChild(stageWrap);

  const overlayDefs = [
    { kind: 'obb', label: 'Bounding box', has: info && info.obb },
    { kind: 'symmetry', label: 'Symmetry axis', has: info && info.symmetry && info.symmetry.axes.length },
    { kind: 'tabletop', label: 'Tabletop poses', has: info && info.tabletop_poses && info.tabletop_poses.length },
  ];
  const ovWrap = document.createElement('div');
  ovWrap.className = 'ctl-group';
  ovWrap.innerHTML = '<div class="ctl-title">Overlays</div>';
  overlayDefs.forEach(d => {
    const lab = document.createElement('label');
    lab.className = 'ctl-check' + (d.has ? '' : ' disabled');
    const tag = d.kind === 'symmetry' && info && info.symmetry ? ` (${info.symmetry.type})` : '';
    lab.innerHTML = `<input type="checkbox" ${d.has ? '' : 'disabled'}> ${d.label}${tag}`;
    if (d.has) lab.querySelector('input').addEventListener('change', e => onOverlay(d.kind, e.target.checked));
    ovWrap.appendChild(lab);
  });
  panel.appendChild(ovWrap);
}

function showError(msg) {
  const loading = document.getElementById('loading');
  if (loading) loading.style.display = 'none';
  document.getElementById('error-msg').textContent = msg;
  document.getElementById('error').style.display = 'block';
}
