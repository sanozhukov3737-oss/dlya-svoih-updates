import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const status = document.getElementById('status');
const stage = document.getElementById('stage');
let renderer, controls, frame, display, displayContext, diagnosticLogged = false, disposed = false;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 100);
let model;
let home;
function fail(message) {
  document.body.dataset.state = 'error';
  status.hidden = false;
  status.textContent = message;
}
function render() {
  frame = null;
  if (!disposed && renderer && !document.hidden) {
    controls.update();
    renderer.render(scene, camera);
    displayContext.drawImage(renderer.domElement, 0, 0, display.width, display.height);
    if (model) {
      document.body.dataset.state = 'ready';
      status.hidden = true;
      display.dataset.triangles = String(renderer.info.render.triangles);
      if (!diagnosticLogged) {
        diagnosticLogged = true;
        const pixels = displayContext.getImageData(0, 0, display.width, display.height).data;
        const colors = new Set();
        for (let i = 0; i < pixels.length; i += 64) colors.add((pixels[i] << 16) | (pixels[i+1] << 8) | pixels[i+2]);
        display.dataset.colors = String(colors.size);
        console.info('Offline model frame', JSON.stringify({colors: colors.size, triangles: renderer.info.render.triangles,
          stage: [stage.clientWidth, stage.clientHeight], viewport: [innerWidth, innerHeight],
          buffer: [display.width, display.height], camera: camera.position.toArray()}));
        if (colors.size < 8) fail('Не удалось отрисовать модель. Закройте 3D-просмотр и попробуйте снова.');
      }
    }
  }
}
function requestRender() {
  if (!frame && !disposed) frame = requestAnimationFrame(render);
}
function resize() {
  if (!renderer) return;
  const width = stage.clientWidth, height = stage.clientHeight;
  if (!width || !height) return;
  const ratio = renderer.getPixelRatio();
  if (renderer.domElement.width !== Math.floor(width * ratio) || renderer.domElement.height !== Math.floor(height * ratio)) {
    renderer.setSize(width, height, false);
    display.width = renderer.domElement.width;
    display.height = renderer.domElement.height;
  }
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  requestRender();
}
function cleanup() {
  if (disposed) return;
  disposed = true;
  cancelAnimationFrame(frame);
  controls?.dispose();
  scene.traverse(object => {
    object.geometry?.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) if (material) {
      for (const value of Object.values(material)) if (value?.isTexture) value.dispose();
      material.dispose();
    }
  });
  renderer?.dispose();
  renderer?.forceContextLoss();
}
async function initialize() {
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setClearColor(0x131a17);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  // Copy each requested GPU frame to a persistent 2D canvas. Older Android WebView
  // can discard or incorrectly composite an on-screen WebGL drawing buffer.
  display = document.createElement('canvas');
  display.setAttribute('aria-label', 'Объёмная модель');
  displayContext = display.getContext('2d', { alpha: false });
  if (!displayContext) throw new Error('Canvas display is unavailable');
  stage.appendChild(display);
  scene.add(new THREE.HemisphereLight(0xf7f6e6, 0x61756a, 2.8));
  for (const [position, intensity] of [[[3, 5, 4], 3.1], [[-4, 2, -2], 1.8], [[0, -3, 1], 0.6]]) {
    const light = new THREE.DirectionalLight(0xffffff, intensity);
    light.position.set(...position); scene.add(light);
  }
  controls = new OrbitControls(camera, display);
  controls.enableDamping = false;
  controls.enablePan = false;
  controls.minDistance = 0.65;
  controls.maxDistance = 4.5;
  controls.addEventListener('change', requestRender);
  renderer.domElement.addEventListener('webglcontextlost', event => {
    event.preventDefault(); fail('Не удалось сохранить 3D-просмотр. Закройте его и откройте снова.');
  });
  window.addEventListener('resize', resize);
  new ResizeObserver(resize).observe(stage);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(frame); frame = null; } else requestRender();
  });
  document.getElementById('reset').addEventListener('click', () => {
    if (!home) return;
    camera.position.copy(home); controls.target.set(0, 0, 0); controls.update(); requestRender();
  });
  const manifestResponse = await fetch('./models.json');
  if (!manifestResponse.ok) throw new Error('Model list is unavailable');
  const manifest = await manifestResponse.json();
  const modelId = location.hash.slice(1) || 'tm-46';
  const selected = manifest.models.find(item => item.id === modelId);
  if (!selected || !/^[a-z0-9-]+\.glb$/.test(selected.file)) throw new Error('Unknown packaged model');
  document.title = selected.title + ' — офлайн 3D';
  display.setAttribute('aria-label', 'Объёмная модель ' + selected.title);
  document.body.dataset.model = selected.id;
  const modelUrl = './' + selected.file;
  const manager = new THREE.LoadingManager();
  manager.setURLModifier(url => {
    // Only this packaged asset and GLB-embedded image blobs are permitted.
    if (url.startsWith('blob:') || url === modelUrl || url === selected.file) return url;
    const parsed = new URL(url, window.location.href);
    if (parsed.origin === window.location.origin && parsed.pathname === '/assets/viewer3d/' + selected.file && !parsed.search) return url;
    throw new Error('External model resource is disabled');
  });
  new GLTFLoader(manager).load(modelUrl, gltf => {
    if (disposed) return;
    model = gltf.scene;
    const box = new THREE.Box3().setFromObject(model);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const scale = 1.4 / Math.max(size.x, size.y, size.z);
    const group = new THREE.Group();
    group.add(model); model.position.sub(center); group.scale.setScalar(scale); scene.add(group);
    home = new THREE.Vector3(1.35, 1.05, 1.75);
    camera.position.copy(home); controls.target.set(0, 0, 0); controls.update(); resize(); requestRender();
  }, undefined, () => fail('Не удалось открыть модель. Закройте 3D-просмотр и попробуйте снова.'));
  resize();
} catch (error) {
  fail('3D-просмотр недоступен. Обновите Android System WebView и откройте карточку снова.');
}
}
initialize();
window.addEventListener('pagehide', cleanup, { once: true });
