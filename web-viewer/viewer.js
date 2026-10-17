import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const status = document.getElementById('status');
const stage = document.getElementById('stage');
let renderer, controls, frame, disposed = false;
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
    if (model) {
      document.body.dataset.state = 'ready';
      status.hidden = true;
      renderer.domElement.dataset.triangles = String(renderer.info.render.triangles);
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
  renderer.setSize(width, height, false);
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
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  renderer.setClearColor(0x131a17);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  renderer.domElement.setAttribute('aria-label', 'Объёмная модель ТМ-46');
  stage.appendChild(renderer.domElement);
  scene.add(new THREE.HemisphereLight(0xf7f6e6, 0x61756a, 2.8));
  for (const [position, intensity] of [[[3, 5, 4], 3.1], [[-4, 2, -2], 1.8], [[0, -3, 1], 0.6]]) {
    const light = new THREE.DirectionalLight(0xffffff, intensity);
    light.position.set(...position); scene.add(light);
  }
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = false;
  controls.enablePan = false;
  controls.minDistance = 0.65;
  controls.maxDistance = 4.5;
  controls.addEventListener('change', requestRender);
  renderer.domElement.addEventListener('webglcontextlost', event => {
    event.preventDefault(); fail('Не удалось сохранить 3D-просмотр. Закройте его и откройте снова.');
  });
  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(frame); frame = null; } else requestRender();
  });
  document.getElementById('reset').addEventListener('click', () => {
    if (!home) return;
    camera.position.copy(home); controls.target.set(0, 0, 0); controls.update(); requestRender();
  });
  const manager = new THREE.LoadingManager();
  manager.setURLModifier(url => {
    // Only this packaged asset and GLB-embedded image blobs are permitted.
    if (url.startsWith('blob:') || url === './tm-46.glb' || url === 'tm-46.glb') return url;
    const parsed = new URL(url, window.location.href);
    if (parsed.origin === window.location.origin && parsed.pathname === '/assets/viewer3d/tm-46.glb') return url;
    throw new Error('External model resource is disabled');
  });
  new GLTFLoader(manager).load('./tm-46.glb', gltf => {
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
window.addEventListener('pagehide', cleanup, { once: true });
