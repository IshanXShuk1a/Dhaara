import type { IntersectionWsPayload } from "./types";

export const SIMULATION_ID = "SIMULATION-LAB";
export type SimulationScenario = "balanced" | "ns_busy" | "ew_busy" | "empty_ew" | "empty_ns";
export type SimulationDirection = "NORTH" | "SOUTH" | "EAST" | "WEST";
export type SimulationSpeed = 1 | 2 | 5 | 10;

export interface SimulationSnapshot extends IntersectionWsPayload {
  simulation?: {
    scenario: SimulationScenario;
    label: string;
    targets: { north: number; south: number; east: number; west: number };
    paused: boolean;
    speed: SimulationSpeed;
    simulated_time_s: number;
    run_id: number;
    ambulance: { direction: SimulationDirection; lights_active: boolean } | null;
  };
}

export const SIMULATION_CASES: Array<{
  id: SimulationScenario; title: string; description: string; lesson: string;
}> = [
  { id: "balanced", title: "Balanced traffic", description: "8 cars from each direction", lesson: "Both pairs have equal demand. East + West and North + South take turns for 70 seconds, with yellow before every change." },
  { id: "ns_busy", title: "North + South busy", description: "18 N/S cars · 4 E/W cars", lesson: "North + South leads by 28 points, so East + West turns yellow before North + South gets green. The next normal green still goes to East + West." },
  { id: "ew_busy", title: "East + West busy", description: "18 E/W cars · 4 N/S cars", lesson: "East + West starts first because its average score leads by 28 points. The next normal green still goes to North + South." },
  { id: "empty_ew", title: "East + West nearly empty", description: "2 E/W cars · 18 N/S cars", lesson: "East + West has 40 seconds left but a score of only 4. After 3 seconds of low demand, yellow leads into a full 70 seconds for North + South." },
  { id: "empty_ns", title: "North + South nearly empty", description: "2 N/S cars · 18 E/W cars", lesson: "North + South has 40 seconds left but a score of only 4. After 3 seconds of low demand, yellow leads into a full 70 seconds for East + West." },
];
