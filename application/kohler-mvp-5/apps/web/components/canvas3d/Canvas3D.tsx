"use client";

import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { LayoutIR, LayoutObject } from "@/lib/types";

const MM_TO_M = 1 / 1000;

/**
 * Finish -> simple PBR-ish material, per plan.md: "simple PBR
 * materials by finish tag. If a mesh is missing, render dimensionally
 * accurate boxes (honest MVP)." No mesh library is wired up here at
 * all \u2014 every object is a box, always, colored by its finish tag from
 * the Layout IR. Reads ONLY the IR (plan.md's sync rule: "any chat
 * modification regenerates IR on the server; clients are read-only
 * views" \u2014 this component never fetches product data separately).
 */
function materialFor(finish: string): { color: string; metalness: number; roughness: number } {
  const f = finish.toLowerCase();
  if (f.includes("chrome") || f.includes("nickel")) return { color: "#c9ced4", metalness: 0.9, roughness: 0.15 };
  if (f.includes("black")) return { color: "#1c1c1e", metalness: 0.6, roughness: 0.35 };
  if (f.includes("gold") || f.includes("brass")) return { color: "#b8935a", metalness: 0.85, roughness: 0.25 };
  if (f.includes("oak") || f.includes("walnut")) return { color: "#8a6a4a", metalness: 0.0, roughness: 0.8 };
  if (f.includes("mirror")) return { color: "#dfe6ea", metalness: 0.95, roughness: 0.05 };
  if (f === "n/a") return { color: "#9ca3af", metalness: 0.1, roughness: 0.6 };
  return { color: "#f5f5f4", metalness: 0.05, roughness: 0.7 }; // white / white acrylic / default
}

function FixtureBox({ obj }: { obj: LayoutObject }) {
  const w = obj.bbox.w * MM_TO_M;
  const h = obj.bbox.h * MM_TO_M;
  const d = obj.bbox.d * MM_TO_M;
  const x = (obj.origin.x + obj.bbox.w / 2) * MM_TO_M;
  const z = (obj.origin.y + obj.bbox.d / 2) * MM_TO_M;
  const mat = materialFor(obj.finish);

  return (
    <mesh position={[x, h / 2, z]} castShadow receiveShadow>
      <boxGeometry args={[w, h, d]} />
      <meshStandardMaterial color={mat.color} metalness={mat.metalness} roughness={mat.roughness} />
    </mesh>
  );
}

function Room({ layoutIr }: { layoutIr: LayoutIR }) {
  const widthM = layoutIr.room.polygon[2][0] * MM_TO_M;
  const depthM = layoutIr.room.polygon[2][1] * MM_TO_M;
  const heightM = layoutIr.room.height_mm * MM_TO_M;

  return (
    <group>
      {/* floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[widthM / 2, 0, depthM / 2]} receiveShadow>
        <planeGeometry args={[widthM, depthM]} />
        <meshStandardMaterial color="#e7e5e4" />
      </mesh>
      {/* back + side walls, thin boxes \u2014 no physics, just orientation cues */}
      <mesh position={[widthM / 2, heightM / 2, 0]}>
        <boxGeometry args={[widthM, heightM, 0.02]} />
        <meshStandardMaterial color="#fafaf9" />
      </mesh>
      <mesh position={[0, heightM / 2, depthM / 2]}>
        <boxGeometry args={[0.02, heightM, depthM]} />
        <meshStandardMaterial color="#fafaf9" />
      </mesh>
    </group>
  );
}

interface Props {
  layoutIr: LayoutIR;
}

export default function Canvas3D({ layoutIr }: Props) {
  const widthM = layoutIr.room.polygon[2][0] * MM_TO_M;
  const depthM = layoutIr.room.polygon[2][1] * MM_TO_M;
  const camDist = Math.max(widthM, depthM) * 1.6;

  return (
    <div style={{ width: "100%", height: "100%", maxHeight: 480 }}>
      <Canvas shadows camera={{ position: [camDist, camDist * 0.8, camDist], fov: 45 }}>
        <Suspense fallback={null}>
          <ambientLight intensity={0.6} />
          <directionalLight position={[3, 5, 2]} intensity={0.8} castShadow />
          <Room layoutIr={layoutIr} />
          {layoutIr.objects.map((obj) => (
            <FixtureBox key={obj.id} obj={obj} />
          ))}
          <OrbitControls target={[widthM / 2, 0.5, depthM / 2]} />
        </Suspense>
      </Canvas>
    </div>
  );
}
