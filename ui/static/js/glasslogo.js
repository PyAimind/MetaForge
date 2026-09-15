// Real-time Three.js scene rendering the MetaForge glass logo.

import * as THREE from "three";
import { FontLoader } from "three/addons/FontLoader.js";
import { TextGeometry } from "three/addons/TextGeometry.js";

const CANVAS_ID = "glasslogo";
const FONT_PATH = "/static/vendor/three/helvetiker_bold.typeface.json";

let _renderer = null;
let _scene = null;
let _camera = null;
let _logoGroup = null;
let _clock = null;
let _rafId = null;
let _resizeObserver = null;
let _initialized = false;

function _createRenderer(canvas) {
  const r = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: "high-performance",
  });
  r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  r.setClearColor(0x000000, 0);
  r.toneMapping = THREE.ACESFilmicToneMapping;
  r.toneMappingExposure = 1.2;
  return r;
}

function _makeEnvTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");

  const grad = ctx.createLinearGradient(0, 0, 0, 512);
  grad.addColorStop(0.00, "#050a18");
  grad.addColorStop(0.35, "#2a4a80");
  grad.addColorStop(0.48, "#c8e0ff");
  grad.addColorStop(0.52, "#ffffff");
  grad.addColorStop(0.65, "#4a6ba8");
  grad.addColorStop(1.00, "#050a18");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 512, 512);

  const glow = ctx.createRadialGradient(160, 120, 10, 160, 120, 140);
  glow.addColorStop(0, "rgba(180, 210, 255, 0.9)");
  glow.addColorStop(1, "rgba(180, 210, 255, 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, 512, 512);

  const glow2 = ctx.createRadialGradient(380, 400, 10, 380, 400, 120);
  glow2.addColorStop(0, "rgba(120, 160, 255, 0.6)");
  glow2.addColorStop(1, "rgba(120, 160, 255, 0)");
  ctx.fillStyle = glow2;
  ctx.fillRect(0, 0, 512, 512);

  return canvas;
}

function _createScene(renderer) {
  const scene = new THREE.Scene();

  const envCanvas = _makeEnvTexture();
  const envTex = new THREE.CanvasTexture(envCanvas);
  envTex.mapping = THREE.EquirectangularReflectionMapping;
  envTex.colorSpace = THREE.SRGBColorSpace;

  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromEquirectangular(envTex).texture;

  return scene;
}

function _createCamera(width, height) {
  const cam = new THREE.PerspectiveCamera(35, width / height, 0.1, 100);
  cam.position.set(0, 0, 10);
  cam.lookAt(0, 0, 0);
  return cam;
}

function _addLights(scene) {
  scene.add(new THREE.AmbientLight(0xffffff, 0.5));

  const key = new THREE.DirectionalLight(0xaaccff, 2.2);
  key.position.set(6, 8, 7);
  scene.add(key);

  const rim = new THREE.DirectionalLight(0xffffff, 1.5);
  rim.position.set(-7, -5, -6);
  scene.add(rim);

  const fill = new THREE.DirectionalLight(0xc8dfff, 0.8);
  fill.position.set(-3, 6, 4);
  scene.add(fill);
}

function _glassMaterial() {
  return new THREE.MeshPhysicalMaterial({
    color: 0xb8d4ff,
    metalness: 0,
    roughness: 0.03,
    transmission: 1,
    thickness: 0.7,
    ior: 1.45,
    envMapIntensity: 2.4,
    clearcoat: 1,
    clearcoatRoughness: 0.02,
    transparent: true,
    opacity: 1,
    emissive: 0x14284a,
    emissiveIntensity: 0.25,
  });
}

function _makeTextMesh(text, font, size, depth, yOffset) {
  const geo = new TextGeometry(text, {
    font,
    size,
    height: depth,
    curveSegments: 12,
    bevelEnabled: true,
    bevelThickness: 0.06,
    bevelSize: 0.035,
    bevelSegments: 6,
  });
  geo.computeBoundingBox();
  const bb = geo.boundingBox;
  const width = bb.max.x - bb.min.x;
  geo.translate(-width / 2, yOffset, 0);
  return new THREE.Mesh(geo, _glassMaterial());
}

function _buildLogo(font) {
  const group = new THREE.Group();
  group.add(_makeTextMesh("Meta", font, 1.9, 0.5, 0.35));
  group.add(_makeTextMesh("Forge", font, 1.9, 0.5, -1.9));
  group.rotation.z = 0.13;
  return group;
}

function _resize() {
  if (!_renderer || !_camera) return;
  const canvas = _renderer.domElement;
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(1, Math.floor(rect.width));
  const h = Math.max(1, Math.floor(rect.height));
  _renderer.setSize(w, h, false);
  _camera.aspect = w / h;
  _camera.updateProjectionMatrix();
}

function _animate() {
  _rafId = requestAnimationFrame(_animate);
  const t = _clock.getElapsedTime();

  if (_logoGroup) {
    _logoGroup.rotation.y = Math.sin(t * 0.35) * 0.20;
    _logoGroup.rotation.x = Math.sin(t * 0.5) * 0.05;
    _logoGroup.position.y = Math.sin(t * 0.8) * 0.08;
  }

  _renderer.render(_scene, _camera);
}

export function initGlassLogo() {
  if (_initialized) return;
  const canvas = document.getElementById(CANVAS_ID);
  if (!canvas) return;

  _renderer = _createRenderer(canvas);
  _scene = _createScene(_renderer);
  _addLights(_scene);

  const w = canvas.clientWidth || 680;
  const h = canvas.clientHeight || 400;
  _camera = _createCamera(w, h);
  _clock = new THREE.Clock();

  _resize();

  _resizeObserver = new ResizeObserver(() => _resize());
  _resizeObserver.observe(canvas);

  const loader = new FontLoader();
  loader.load(
    FONT_PATH,
    (font) => {
      _logoGroup = _buildLogo(font);
      _scene.add(_logoGroup);
      _animate();
    },
    undefined,
    (err) => {
      console.error("Failed to load MetaForge font:", err);
    }
  );

  _initialized = true;
}

export function destroyGlassLogo() {
  if (_rafId !== null) {
    cancelAnimationFrame(_rafId);
    _rafId = null;
  }
  if (_resizeObserver) {
    _resizeObserver.disconnect();
    _resizeObserver = null;
  }
  if (_renderer) {
    _renderer.dispose();
    _renderer = null;
  }
  _scene = null;
  _camera = null;
  _logoGroup = null;
  _clock = null;
  _initialized = false;
}