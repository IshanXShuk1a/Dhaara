"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { SimulationDirection, SimulationSnapshot } from "@/lib/simulation";

type LightColor = "GREEN" | "YELLOW" | "RED";
const APPROACHES: Array<{ direction: SimulationDirection; dx: number; dz: number; label: string }> = [
  { direction: "NORTH", dx: 0, dz: 1, label: "N" },
  { direction: "SOUTH", dx: 0, dz: -1, label: "S" },
  { direction: "EAST", dx: -1, dz: 0, label: "E" },
  { direction: "WEST", dx: 1, dz: 0, label: "W" },
];
const COLORS = [0x5ba9ee, 0xf3b950, 0xf17469, 0x9c8ce6, 0x56c7b0, 0xe8edf3];
interface Car { mesh: THREE.Group; direction: SimulationDirection; lane: number; distance: number; committed: boolean; ambulance: boolean; beacons: THREE.MeshStandardMaterial[] }

export default function IntersectionScene({ snapshot, running, view, resetView }: {
  snapshot: SimulationSnapshot | null; running: boolean; view: "perspective" | "overhead"; resetView: number;
}) {
  const host = useRef<HTMLDivElement>(null);
  const live = useRef({ snapshot, running });
  live.current = { snapshot, running };
  const cameraControl = useRef<(() => void) | null>(null);
  const viewRef = useRef(view);
  viewRef.current = view;
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { cameraControl.current?.(); }, [view, resetView]);

  useEffect(() => {
    const container = host.current;
    if (!container) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "low-power" }); }
    catch { setError("3D needs WebGL 2. Enable browser graphics acceleration to explore the intersection. The signal controls below remain available."); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setClearColor(0xdce7f0);
    renderer.domElement.setAttribute("aria-label", "Interactive 3D four-way traffic intersection");
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.style.touchAction = "none";
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0xdce7f0, 130, 260);
    const camera = new THREE.PerspectiveCamera(41, 1, 0.1, 300);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minDistance = 32;
    controls.maxDistance = 140;
    controls.minPolarAngle = 0.04;
    controls.maxPolarAngle = Math.PI / 2.25;
    const setView = () => {
      controls.target.set(0, 0, 0);
      camera.position.set(...(viewRef.current === "overhead" ? [0, 105, 0.1] : [62, 66, 76]) as [number, number, number]);
      controls.update();
    };
    cameraControl.current = setView;
    setView();
    scene.add(new THREE.HemisphereLight(0xf4f8ff, 0x81957e, 2.4));
    const sun = new THREE.DirectionalLight(0xfff5df, 3);
    sun.position.set(-25, 55, 30);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    Object.assign(sun.shadow.camera, { left: -44, right: 44, top: 44, bottom: -44, near: 1, far: 120 });
    sun.shadow.normalBias = 0.05;
    scene.add(sun);

    const geometries = new Set<THREE.BufferGeometry>();
    const materials = new Set<THREE.Material>();
    const textures = new Set<THREE.Texture>();
    const materialCache = new Map<number, THREE.MeshStandardMaterial>();
    const boxGeometryCache = new Map<string, THREE.BoxGeometry>();
    const material = (color: number) => {
      let result = materialCache.get(color);
      if (!result) { result = new THREE.MeshStandardMaterial({ color, roughness: 0.8 }); materialCache.set(color, result); materials.add(result); }
      return result;
    };
    const box = (w: number, h: number, d: number, color: number, x: number, y: number, z: number, parent: THREE.Object3D = scene) => {
      const key = `${w},${h},${d}`;
      let geometry = boxGeometryCache.get(key);
      if (!geometry) { geometry = new THREE.BoxGeometry(w, h, d); geometries.add(geometry); boxGeometryCache.set(key, geometry); }
      const mesh = new THREE.Mesh(geometry, material(color));
      mesh.position.set(x, y, z); mesh.castShadow = h > 0.3; mesh.receiveShadow = true; parent.add(mesh); return mesh;
    };
    box(86, 1.1, 86, 0xadc4b1, 0, -0.65, 0);
    box(83, 0.15, 83, 0xc9d7c3, 0, -0.03, 0);
    box(10, 0.15, 83, 0x394756, 0, 0.08, 0);
    box(83, 0.15, 10, 0x394756, 0, 0.09, 0);
    // Raised pavements keep the road boundary and crossings visible from every angle.
    for (const x of [-24, 24]) for (const z of [-24, 24]) {
      box(35, 0.32, 35, 0xe5e6dd, x, 0.1, z);
      box(32, 0.1, 32, 0xb5cfa3, x, 0.31, z);
    }
    for (const approach of APPROACHES) {
      const group = new THREE.Group(); group.rotation.y = Math.atan2(approach.dx, approach.dz); scene.add(group);
      // Two incoming lanes, two outgoing lanes. Indian left-hand traffic.
      for (let d = 11; d < 40; d += 4) {
        box(0.1, 0.03, 2, 0x8996a3, 2.5, 0.2, -d, group);
        box(0.1, 0.03, 2, 0x8996a3, -2.5, 0.2, -d, group);
        box(0.11, 0.03, 2, 0xf1cb70, -0.17, 0.21, -d, group);
        box(0.11, 0.03, 2, 0xf1cb70, 0.17, 0.21, -d, group);
      }
      for (let x = -4.3; x < 5; x += 1.05) box(0.62, 0.04, 1.55, 0xf5f3e8, x, 0.22, -6.4, group);
      box(4.6, 0.04, 0.18, 0xffffff, 2.5, 0.23, -7.7, group);
      // Direction label is a billboard rather than an ambiguous screen compass.
      const labelCanvas = document.createElement("canvas"); labelCanvas.width = 128; labelCanvas.height = 128;
      const ctx = labelCanvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#20364d"; ctx.beginPath(); ctx.roundRect(8, 8, 112, 112, 28); ctx.fill();
        ctx.fillStyle = "#ffffff"; ctx.font = "bold 76px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(approach.label, 64, 66);
        const texture = new THREE.CanvasTexture(labelCanvas); textures.add(texture);
        const labelMaterial = new THREE.SpriteMaterial({ map: texture, depthTest: false }); materials.add(labelMaterial);
        const sprite = new THREE.Sprite(labelMaterial); sprite.scale.set(4.6, 4.6, 1); sprite.position.set(-approach.dx * 38, 3.8, -approach.dz * 38); scene.add(sprite);
      }
    }
    // Small buildings and parks make the intersection a legible miniature town.
    for (const [index, x, z, h, color] of [
      [0, -20, -23, 8, 0x7fa7be], [1, -31, -18, 5, 0xd2af8c], [2, 22, -25, 10, 0x98abc5],
      [3, 32, -19, 5, 0xe0c6a3], [4, -25, 26, 6, 0xc99c9c], [5, 27, 28, 7, 0x9cb9ad],
    ]) {
      box(8, h, 7, color, x, h / 2 + 0.4, z);
      box(8.7, 0.45, 7.7, 0xf0ece1, x, h + 0.55, z);
      for (let floor = 1.7; floor < h; floor += 2) for (const offset of [-2.5, 0, 2.5]) {
        box(1.1, 1.1, 0.04, 0x48697f, x + offset, floor + 0.5, z + 3.52);
        box(0.04, 1.1, 1.1, 0x48697f, x + 4.02, floor + 0.5, z + offset);
      }
      void index;
    }
    const trunkGeometry = new THREE.CylinderGeometry(0.3, 0.4, 2.5, 6); geometries.add(trunkGeometry);
    const treeGeometry = new THREE.IcosahedronGeometry(2.1, 0); geometries.add(treeGeometry);
    for (const [x, z] of [[-12,-14],[-15,-34],[12,-15],[34,-32],[-12,14],[-34,34],[13,13],[35,13],[-34,-34],[13,35]]) {
      const trunk = new THREE.Mesh(trunkGeometry, material(0x8a6c4e)); trunk.position.set(x, 1.6, z); trunk.castShadow = true; scene.add(trunk);
      const crown = new THREE.Mesh(treeGeometry, material(0x71a577)); crown.position.set(x, 4, z); crown.castShadow = true; scene.add(crown);
    }

    const lamps = new Map<SimulationDirection, Record<LightColor, THREE.MeshStandardMaterial>>();
    const lampGeometry = new THREE.SphereGeometry(0.38, 12, 8); geometries.add(lampGeometry);
    for (const a of APPROACHES) {
      const pole = new THREE.Group(); pole.rotation.y = Math.atan2(a.dx, a.dz); scene.add(pole);
      box(0.2, 6.3, 0.2, 0x485366, 5.7, 3.35, -7.8, pole);
      box(3.4, 0.18, 0.18, 0x485366, 4.1, 6.45, -7.8, pole);
      box(1.15, 3.1, 0.75, 0x1e2936, 2.5, 5.1, -7.8, pole);
      const colors = { RED: 0xff505a, YELLOW: 0xffca43, GREEN: 0x45e4a0 };
      const pair = {} as Record<LightColor, THREE.MeshStandardMaterial>;
      (["RED", "YELLOW", "GREEN"] as LightColor[]).forEach((c, index) => {
        const m = new THREE.MeshStandardMaterial({ color: colors[c], emissive: colors[c], emissiveIntensity: 0, roughness: 0.35 }); materials.add(m); pair[c] = m;
        const lamp = new THREE.Mesh(lampGeometry, m); lamp.scale.z = 0.65; lamp.position.set(2.5, 6.12 - index * 1.02, -8.23); pole.add(lamp);
        // Matching rear lens makes the signal readable while orbiting the town.
        const rear = new THREE.Mesh(lampGeometry, m); rear.scale.z = 0.65; rear.position.set(2.5, 6.12 - index * 1.02, -7.37); pole.add(rear);
      });
      lamps.set(a.direction, pair);
    }

    const wheelGeometry = new THREE.CylinderGeometry(0.29, 0.29, 0.16, 10); geometries.add(wheelGeometry);
    const beaconGeometry = new THREE.BoxGeometry(0.45, 0.23, 0.35); geometries.add(beaconGeometry);
    const vehicleGroup = new THREE.Group(); scene.add(vehicleGroup);
    let cars: Car[] = [];
    let caseKey = "";
    const makeCar = (direction: SimulationDirection, i: number, ambulance = false): Car => {
      const car = new THREE.Group();
      const body = ambulance ? 0xf7fafc : COLORS[(i + APPROACHES.findIndex(a => a.direction === direction) * 2) % COLORS.length];
      box(1.4, 0.53, 2.5, body, 0, 0.6, 0, car);
      box(1.13, ambulance ? 1.05 : 0.54, ambulance ? 1.9 : 1.32, ambulance ? 0xf7fafc : 0x284d66, 0, ambulance ? 1.08 : 1.1, -0.1, car);
      if (!ambulance) box(1.2, 0.13, 0.88, body, 0, 1.39, -0.14, car);
      for (const x of [-0.71, 0.71]) for (const z of [-0.8, 0.8]) {
        const wheel = new THREE.Mesh(wheelGeometry, material(0x25303d)); wheel.rotation.z = Math.PI / 2; wheel.position.set(x, 0.35, z); car.add(wheel);
      }
      box(1.1, 0.13, 0.04, 0xffedb0, 0, 0.7, 1.27, car);
      box(1.1, 0.12, 0.04, 0xea6173, 0, 0.7, -1.27, car);
      const beacons: THREE.MeshStandardMaterial[] = [];
      if (ambulance) {
        box(0.05, 0.27, 0.8, 0xf45862, 0.72, 1.02, -0.2, car);
        box(0.05, 0.8, 0.25, 0xf45862, 0.72, 1.02, -0.2, car);
        for (const [index, color] of [0x489dff, 0xff5362].entries()) {
          const m = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0 }); materials.add(m); beacons.push(m);
          const beacon = new THREE.Mesh(beaconGeometry, m); beacon.position.set(index ? 0.3 : -0.3, 1.76, -0.1); car.add(beacon);
        }
      }
      vehicleGroup.add(car);
      const a = APPROACHES.find(a => a.direction === direction)!;
      car.rotation.y = Math.atan2(a.dx, a.dz);
      return { mesh: car, direction, lane: ambulance ? 0 : i % 2, distance: ambulance ? 9 : 9 + Math.floor(i / 2) * 3.15, committed: false, ambulance, beacons };
    };
    const rebuild = (data: SimulationSnapshot) => {
      cars.forEach(car => car.beacons.forEach(m => { m.dispose(); materials.delete(m); }));
      // Box geometry/materials are shared between every vehicle and scenario.
      vehicleGroup.clear(); cars = [];
      for (const a of APPROACHES) {
        const count = data.simulation?.targets[a.direction.toLowerCase() as "north"] ?? 0;
        for (let i = 0; i < count; i++) cars.push(makeCar(a.direction, i));
      }
      const ambulance = data.simulation?.ambulance;
      if (ambulance) {
        cars.filter(c => c.direction === ambulance.direction && c.lane === 0).forEach(c => { c.distance += 3.15; });
        cars.push(makeCar(ambulance.direction, 0, true));
      }
      renderer.domElement.dataset.vehicleCount = String(cars.length);
    };
    const resize = () => {
      const { width, height } = container.getBoundingClientRect();
      renderer.setSize(Math.max(1, width), Math.max(1, height)); camera.aspect = width / Math.max(1, height); camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize); observer.observe(container); resize();
    let frame = 0, lastTime = performance.now(), visualTime = 0;
    const animate = (time: number) => {
      frame = requestAnimationFrame(animate);
      const wallDt = Math.min((time - lastTime) / 1000, 0.08); lastTime = time;
      const { snapshot: data, running: connected } = live.current;
      const paused = !connected || !data?.signal || Boolean(data.simulation?.paused);
      const dt = paused ? 0 : wallDt * (data?.simulation?.speed ?? 1);
      visualTime += dt;
      if (data?.simulation) {
        const nextKey = JSON.stringify([data.simulation.scenario, data.simulation.targets, data.simulation.ambulance?.direction, data.simulation.ambulance?.lights_active, data.simulation.run_id]);
        if (nextKey !== caseKey) { rebuild(data); caseKey = nextKey; }
      }
      for (const a of APPROACHES) {
        const color = connected ? data?.signal?.directions[a.direction] : undefined;
        const pairName = a.direction === "EAST" || a.direction === "WEST" ? "EW" : "NS";
        // Delayed broadcasts or a slow graphics frame must not let a new pair
        // enter while an outgoing car is still physically clearing the town.
        const junctionClear = !cars.some(c => (c.direction === "EAST" || c.direction === "WEST" ? "EW" : "NS") !== pairName && c.committed && c.distance > -9 && c.distance < 9);
        const pair = lamps.get(a.direction)!;
        for (const c of ["RED", "YELLOW", "GREEN"] as LightColor[]) { pair[c].emissiveIntensity = color === c ? 3 : 0; pair[c].color.setHex(color === c ? ({ RED: 0xff505a, YELLOW: 0xffca43, GREEN: 0x45e4a0 })[c] : 0x283743); }
        for (const lane of [0, 1]) {
          const queue = cars.filter(c => c.direction === a.direction && c.lane === lane).sort((c, d) => c.distance - d.distance);
          let preceding = -Infinity;
          for (const car of queue) {
            const minimum = Math.max(preceding + 3.15, (color !== "GREEN" || !junctionClear) && !car.committed ? 9 : -Infinity);
            car.distance = Math.max(minimum, car.distance - dt * 6.6);
            if (car.distance < 9) car.committed = true;
            preceding = car.distance;
          }
          for (const car of queue) if (car.distance < -41) {
            car.distance = Math.max(20, ...queue.filter(c => c !== car).map(c => c.distance + 3.15)); car.committed = false;
          }
        }
      }
      for (const car of cars) {
        const a = APPROACHES.find(a => a.direction === car.direction)!;
        const offset = car.lane === 0 ? 1.25 : 3.65;
        car.mesh.position.set(-a.dx * car.distance + a.dz * offset, 0.2, -a.dz * car.distance - a.dx * offset);
        car.mesh.visible = Math.abs(car.distance) < 41;
        car.beacons.forEach((m, i) => { m.emissiveIntensity = data?.simulation?.ambulance?.lights_active && Math.floor(visualTime * 4) % 2 === i ? 4 : 0; });
      }
      renderer.domElement.dataset.signalState = connected ? data?.signal?.state ?? "WAITING" : "DISCONNECTED";
      renderer.domElement.dataset.motion = paused ? "paused" : "running";
      renderer.domElement.dataset.motionTime = visualTime.toFixed(2);
      renderer.domElement.dataset.crossingPairs = Array.from(new Set(cars.filter(c => c.committed && c.distance > -9 && c.distance < 9).map(c => c.direction === "EAST" || c.direction === "WEST" ? "EW" : "NS"))).join(",");
      controls.update(); renderer.render(scene, camera);
    };
    frame = requestAnimationFrame(animate);
    const contextLost = (event: Event) => { event.preventDefault(); setError("Browser graphics were interrupted. Reload the page to restore 3D; signal controls remain available."); };
    renderer.domElement.addEventListener("webglcontextlost", contextLost);
    return () => {
      cancelAnimationFrame(frame); observer.disconnect(); controls.dispose(); cameraControl.current = null;
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose()); textures.forEach(t => t.dispose());
      renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
    };
  }, []);

  return <div ref={host} className="relative h-[350px] w-full overflow-hidden bg-[#dce7f0] sm:h-[440px] xl:h-[min(58vh,620px)]" data-testid="intersection-scene">
    {error && <div role="alert" className="absolute inset-0 z-10 flex items-center justify-center bg-surface-panel/95 p-8 text-center text-sm text-text-secondary">{error}</div>}
  </div>;
}
