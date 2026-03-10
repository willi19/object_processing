const HF_BASE = 'https://huggingface.co/datasets/willi19/object_processing/resolve/main/';

(async function () {
  const params = new URLSearchParams(window.location.search);
  const objectId = params.get('id');

  if (!objectId) {
    showError('No object ID specified.');
    return;
  }

  // Load catalog
  let catalog;
  try {
    const res = await fetch('catalog.json');
    catalog = await res.json();
  } catch (e) {
    showError('Failed to load catalog.');
    return;
  }

  const obj = catalog.objects.find(o => o.id === objectId);
  if (!obj) {
    showError(`Object "${objectId}" not found in catalog.`);
    return;
  }

  // Update UI
  document.getElementById('obj-label').textContent = obj.label;
  document.title = `${obj.label} - Object Viewer`;

  if (obj.category) {
    const catEl = document.getElementById('obj-category');
    catEl.textContent = obj.category;
    catEl.style.display = '';
  }

  const glbUrl = HF_BASE + obj.url;
  const dlLink = document.getElementById('download-link');
  dlLink.href = glbUrl;
  dlLink.style.display = '';

  // Init Babylon.js
  const canvas = document.getElementById('renderCanvas');
  const engine = new BABYLON.Engine(canvas, true, { preserveDrawingBuffer: true, stencil: true });
  const scene = new BABYLON.Scene(engine);

  scene.clearColor = new BABYLON.Color4(0.051, 0.067, 0.09, 1); // #0d1117

  // Camera
  const camera = new BABYLON.ArcRotateCamera('cam', Math.PI / 4, Math.PI / 3, 2, BABYLON.Vector3.Zero(), scene);
  camera.attachControl(canvas, true);
  camera.wheelPrecision = 50;
  camera.minZ = 0.01;
  camera.lowerRadiusLimit = 0.1;
  camera.upperRadiusLimit = 50;
  camera.lowerBetaLimit = 0;        // allow looking from directly above
  camera.upperBetaLimit = Math.PI;   // allow looking from directly below

  // Lights
  const hemi = new BABYLON.HemisphericLight('hemi', new BABYLON.Vector3(0, 1, 0), scene);
  hemi.intensity = 0.8;

  const dir = new BABYLON.DirectionalLight('dir', new BABYLON.Vector3(-1, -2, 1), scene);
  dir.intensity = 0.6;

  // Load GLB — split into rootUrl + filename so Babylon.js detects .glb extension
  try {
    const rootUrl = HF_BASE + obj.url.replace('mesh.glb', '');
    const container = await BABYLON.SceneLoader.LoadAssetContainerAsync(
      rootUrl, 'mesh.glb', scene
    );
    container.addAllToScene();

    // Fit camera to loaded meshes
    const meshes = container.meshes.filter(m => m.getTotalVertices() > 0);
    if (meshes.length > 0) {
      let min = new BABYLON.Vector3(Infinity, Infinity, Infinity);
      let max = new BABYLON.Vector3(-Infinity, -Infinity, -Infinity);

      meshes.forEach(m => {
        m.computeWorldMatrix(true);
        const bounds = m.getBoundingInfo().boundingBox;
        min = BABYLON.Vector3.Minimize(min, bounds.minimumWorld);
        max = BABYLON.Vector3.Maximize(max, bounds.maximumWorld);
      });

      const center = BABYLON.Vector3.Center(min, max);
      const extent = max.subtract(min);
      const radius = extent.length() / 2;

      camera.target = center;
      camera.radius = radius * 2.5;
    }

    document.getElementById('loading').style.display = 'none';
  } catch (e) {
    console.error('Failed to load GLB:', e);
    showError(`Failed to load 3D model: ${e.message || e}`);
  }

  // Render loop
  engine.runRenderLoop(() => scene.render());
  window.addEventListener('resize', () => engine.resize());
})();

function showError(msg) {
  const loading = document.getElementById('loading');
  if (loading) loading.style.display = 'none';
  document.getElementById('error-msg').textContent = msg;
  document.getElementById('error').style.display = 'block';
}
