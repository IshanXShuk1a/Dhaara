"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { createSceneVisuals, SIGNAL_COLORS, type SceneLighting, type LightColor } from "./sceneVisuals";
import type { SimulationDirection, SimulationSnapshot } from "@/lib/simulation";

const APPROACHES: Array<{ direction: SimulationDirection; dx: number; dz: number; label: string }> = [
  { direction: "NORTH", dx: 0, dz: 1, label: "N" },
  { direction: "SOUTH", dx: 0, dz: -1, label: "S" },
  { direction: "EAST", dx: -1, dz: 0, label: "E" },
  { direction: "WEST", dx: 1, dz: 0, label: "W" },
];
const COLORS = [0x327e96, 0xe9b64f, 0xb94f51, 0x78869b, 0x547c6b, 0xe7e2d7];
interface Car { mesh: THREE.Group; direction: SimulationDirection; lane: number; distance: number; committed: boolean; ambulance: boolean; beacons: THREE.MeshStandardMaterial[] }

export default function IntersectionScene({ snapshot, running, view, resetView, lighting = "sunset" }: {
  snapshot: SimulationSnapshot | null; running: boolean; view: "perspective" | "overhead"; resetView: number; lighting?: SceneLighting;
}) {
  const host = useRef<HTMLDivElement>(null);
  const live = useRef({ snapshot, running });
  live.current = { snapshot, running };
  const cameraControl = useRef<(() => void) | null>(null);
  const visualControls = useRef<((lighting: SceneLighting) => void) | null>(null);
  const lightingRef = useRef(lighting); lightingRef.current = lighting;
  const viewRef = useRef(view);
  viewRef.current = view;
  const [error, setError] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);

  useEffect(() => { cameraControl.current?.(); }, [view, resetView]);
  useEffect(() => { visualControls.current?.(lighting); }, [lighting]);
  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement === host.current);
    document.addEventListener("fullscreenchange", update);
    return () => document.removeEventListener("fullscreenchange", update);
  }, []);

  useEffect(() => {
    const container = host.current;
    if (!container) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" }); }
    catch { setError("3D needs WebGL 2. Enable browser graphics acceleration to explore the intersection. The signal controls below remain available."); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.12;
    renderer.domElement.setAttribute("aria-label", "Interactive 3D four-way traffic intersection");
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.style.touchAction = "none";
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 600);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minDistance = 32;
    controls.maxDistance = 125;
    controls.minPolarAngle = 0.04;
    controls.maxPolarAngle = Math.PI / 2.25;
    let cameraTransition: { from: THREE.Vector3; to: THREE.Vector3; start: number } | null = null;
    let initialView = true;
    const setView = () => {
      controls.target.set(0, 1, 0);
      const target = new THREE.Vector3(...(viewRef.current === "overhead" ? [0, 100, 0.1] : [48, 43, 56]) as [number, number, number]);
      if (initialView) { camera.position.copy(target); initialView = false; }
      else cameraTransition = { from: camera.position.clone(), to: target, start: performance.now() };
      controls.update();
    };
    const stopCameraTransition = () => { cameraTransition = null; };
    controls.addEventListener("start", stopCameraTransition);
    cameraControl.current = setView;
    setView();
    const visuals = createSceneVisuals(scene, renderer);
    const { lamps, materials } = visuals;
    visualControls.current = visuals.setLighting;
    visuals.setLighting(lightingRef.current);

    const vehicleGroup = new THREE.Group(); scene.add(vehicleGroup);
    let cars: Car[] = [];
    let caseKey = "";
    const makeCar = (direction: SimulationDirection, i: number, ambulance = false): Car => {
      const body = ambulance ? 0xf7fafc : COLORS[(i + APPROACHES.findIndex(a => a.direction === direction) * 2) % COLORS.length];
      const { mesh: car, beacons } = visuals.createVehicle(body, i, ambulance);
      vehicleGroup.add(car);
      const a = APPROACHES.find(a => a.direction === direction)!;
      car.rotation.y = Math.atan2(a.dx, a.dz);
      return { mesh: car, direction, lane: ambulance ? 0 : i % 2, distance: ambulance ? 9 : 9 + Math.floor(i / 2) * 3.15, committed: false, ambulance, beacons };
    };
    const rebuild = (data: SimulationSnapshot) => {
      cars.forEach(car => car.beacons.forEach(m => { m.dispose(); materials.delete(m); }));
      // Vehicle geometry/materials are shared between every vehicle and scenario.
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
        const nextKey = JSON.stringify([data.simulation.session_id, data.simulation.scenario, data.simulation.targets, data.simulation.ambulance?.direction, data.simulation.run_id]);
        if (nextKey !== caseKey) { rebuild(data); caseKey = nextKey; }
      }
      for (const a of APPROACHES) {
        const color = connected ? data?.signal?.directions[a.direction] : undefined;
        const pairName = a.direction === "EAST" || a.direction === "WEST" ? "EW" : "NS";
        // Delayed broadcasts or a slow graphics frame must not let a new pair
        // enter while an outgoing car is still physically clearing the town.
        const junctionClear = !cars.some(c => (c.direction === "EAST" || c.direction === "WEST" ? "EW" : "NS") !== pairName && c.committed && c.distance > -9 && c.distance < 9);
        const pair = lamps.get(a.direction)!;
        for (const c of ["RED", "YELLOW", "GREEN"] as LightColor[]) { pair[c].emissiveIntensity = color === c ? 3 : 0; pair[c].color.setHex(color === c ? SIGNAL_COLORS[c] : 0x283743); }
        visuals.updateSignalGlow(a.direction, color);
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
      if (cameraTransition) {
        const t = Math.min(1, (time - cameraTransition.start) / 700);
        camera.position.lerpVectors(cameraTransition.from, cameraTransition.to, t * t * (3 - 2 * t));
        if (t === 1) cameraTransition = null;
      }
      controls.update(); renderer.render(scene, camera);
      renderer.domElement.dataset.lighting = lightingRef.current;
      renderer.domElement.dataset.renderCalls = String(renderer.info.render.calls);
    };
    frame = requestAnimationFrame(animate);
    const contextLost = (event: Event) => { event.preventDefault(); setError("Browser graphics were interrupted. Reload the page to restore 3D; signal controls remain available."); };
    renderer.domElement.addEventListener("webglcontextlost", contextLost);
    return () => {
      cancelAnimationFrame(frame); observer.disconnect(); controls.dispose(); cameraControl.current = null;
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      visualControls.current = null; visuals.dispose();
      renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
    };
  }, []);

  return <div ref={host} className="relative h-[390px] w-full overflow-hidden bg-[#8babae] sm:h-[490px] xl:h-[min(64vh,700px)] [&:fullscreen]:h-screen [&:fullscreen]:bg-[#101b35]" data-testid="intersection-scene">
    <button type="button" aria-label={fullscreen ? "Exit 3D fullscreen" : "Expand 3D scene"} onClick={() => {
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
      else host.current?.requestFullscreen?.().catch(() => {});
    }} className="absolute right-3 top-3 z-10 grid h-9 w-9 place-items-center rounded-xl border border-white/20 bg-slate-950/55 text-white shadow-lg backdrop-blur-md transition-colors hover:bg-slate-950/80" title={fullscreen ? "Exit fullscreen" : "Expand 3D scene"}>
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M7 3H3v4m10-4h4v4M3 13v4h4m10-4v4h-4" /></svg>
    </button>
    {error && <div role="alert" className="absolute inset-0 z-10 flex items-center justify-center bg-surface-panel/95 p-8 text-center text-sm text-text-secondary">{error}</div>}
  </div>;
}
