"use client";

import type { LayoutIR } from "@/lib/types";

const CATEGORY_COLOR: Record<string, string> = {
  toilet: "#93c5fd",
  vanity: "#fcd34d",
  faucet: "#a7f3d0",
  shower: "#c4b5fd",
  bath: "#fca5a5",
  storage: "#d4d4d4",
};

interface Props {
  layoutIr: LayoutIR;
}

/**
 * SVG 2D plan renderer: draws the room polygon and each placed
 * fixture from the Layout IR, at 1 SVG unit = 1mm, scaled to fit.
 * Per plan.md this is the MVP-must-have feasibility proof — no
 * canvas/WebGL needed for Phase 1.
 */
export default function Canvas2D({ layoutIr }: Props) {
  const room = layoutIr.room;
  const [minX, minY] = room.polygon[0];
  const maxX = Math.max(...room.polygon.map((p) => p[0]));
  const maxY = Math.max(...room.polygon.map((p) => p[1]));
  const pad = 200;
  const viewW = maxX - minX + pad * 2;
  const viewH = maxY - minY + pad * 2;

  return (
    <svg
      viewBox={`${-pad} ${-pad} ${viewW} ${viewH}`}
      className="h-full w-full"
      style={{ maxHeight: 480 }}
    >
      {/* room outline */}
      <polygon
        points={room.polygon.map((p) => p.join(",")).join(" ")}
        fill="#fafafa"
        stroke="#171717"
        strokeWidth={20}
      />

      {/* wet wall hatch */}
      {layoutIr.wet_walls.includes("N") && (
        <line x1={0} y1={0} x2={maxX} y2={0} stroke="#0ea5e9" strokeWidth={40} strokeDasharray="60,30" />
      )}

      {/* fixtures */}
      {layoutIr.objects.map((obj) => (
        <g key={obj.id}>
          <rect
            x={obj.origin.x}
            y={obj.origin.y}
            width={obj.bbox.w}
            height={obj.bbox.d}
            fill={CATEGORY_COLOR[obj.category] ?? "#e5e5e5"}
            stroke="#404040"
            strokeWidth={8}
          />
          <text
            x={obj.origin.x + obj.bbox.w / 2}
            y={obj.origin.y + obj.bbox.d / 2}
            fontSize={60}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="#171717"
          >
            {obj.category}
          </text>
        </g>
      ))}
    </svg>
  );
}
