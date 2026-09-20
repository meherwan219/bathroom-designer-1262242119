"use client";

import { useState, type FormEvent } from "react";
import type { DesignSpecPayload } from "@/lib/types";
import FloorplanUpload from "./FloorplanUpload";

const CATEGORIES = ["toilet", "vanity", "faucet", "shower", "bath", "storage"] as const;
const STYLES = ["modern", "classic", "minimal", "luxury", "transitional", "industrial"] as const;

interface Props {
  onSubmit: (spec: DesignSpecPayload) => void;
  submitting: boolean;
  enableVision: boolean;
}

/**
 * IntakePanel \u2014 W, D, budget, required products, style preferences,
 * and constraints profile. Style/feature preferences feed the
 * recommend engine's weighted soft scoring (Phase 3); profile changes
 * which clearance minimums the constraint engine enforces. Room
 * width/depth can also be pre-filled from an optional floor-plan
 * photo (Phase 4) \u2014 but only after the person explicitly confirms
 * the draft reading; nothing from the image writes here on its own.
 */
export default function IntakePanel({ onSubmit, submitting, enableVision }: Props) {
  const [widthMm, setWidthMm] = useState(2400);
  const [depthMm, setDepthMm] = useState(2700);
  const [budget, setBudget] = useState(300000);
  const [required, setRequired] = useState<string[]>(["toilet", "vanity", "faucet"]);
  const [styles, setStyles] = useState<string[]>([]);
  const [profile, setProfile] = useState<"nkba_std" | "compact_apt">("nkba_std");

  function toggleFrom(list: string[], setList: (v: string[]) => void, value: string) {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit({
      room: { width_mm: widthMm, depth_mm: depthMm, wet_walls: ["N"] },
      budget: { max_inr: budget },
      hard_required: required,
      preferences: { styles },
      constraints_profile: profile,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 text-sm">
      <div>
        <label className="mb-1 block font-medium">Room width (mm)</label>
        <input
          type="number"
          value={widthMm}
          onChange={(e) => setWidthMm(Number(e.target.value))}
          className="w-full rounded border px-2 py-1"
          min={500}
          step={50}
        />
      </div>
      <div>
        <label className="mb-1 block font-medium">Room depth (mm)</label>
        <input
          type="number"
          value={depthMm}
          onChange={(e) => setDepthMm(Number(e.target.value))}
          className="w-full rounded border px-2 py-1"
          min={500}
          step={50}
        />
      </div>

      {enableVision && (
        <FloorplanUpload
          onConfirm={(w, d) => {
            setWidthMm(w);
            setDepthMm(d);
          }}
        />
      )}

      <div>
        <label className="mb-1 block font-medium">Budget (\u20b9)</label>
        <input
          type="number"
          value={budget}
          onChange={(e) => setBudget(Number(e.target.value))}
          className="w-full rounded border px-2 py-1"
          min={0}
          step={1000}
        />
      </div>
      <div>
        <label className="mb-1 block font-medium">Required products</label>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((cat) => (
            <button
              type="button"
              key={cat}
              onClick={() => toggleFrom(required, setRequired, cat)}
              className={`rounded-full border px-3 py-1 text-xs capitalize ${
                required.includes(cat)
                  ? "border-neutral-900 bg-neutral-900 text-white"
                  : "border-neutral-300 text-neutral-600"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>
      <div>
        <label className="mb-1 block font-medium">Style preferences</label>
        <div className="flex flex-wrap gap-2">
          {STYLES.map((style) => (
            <button
              type="button"
              key={style}
              onClick={() => toggleFrom(styles, setStyles, style)}
              className={`rounded-full border px-3 py-1 text-xs capitalize ${
                styles.includes(style)
                  ? "border-emerald-700 bg-emerald-700 text-white"
                  : "border-neutral-300 text-neutral-600"
              }`}
            >
              {style}
            </button>
          ))}
        </div>
      </div>
      <div>
        <label className="mb-1 block font-medium">Room profile</label>
        <div className="flex gap-2">
          {(["nkba_std", "compact_apt"] as const).map((p) => (
            <button
              type="button"
              key={p}
              onClick={() => setProfile(p)}
              className={`rounded-full border px-3 py-1 text-xs ${
                profile === p
                  ? "border-neutral-900 bg-neutral-900 text-white"
                  : "border-neutral-300 text-neutral-600"
              }`}
            >
              {p === "nkba_std" ? "Standard (NKBA)" : "Compact apartment"}
            </button>
          ))}
        </div>
      </div>
      <button
        type="submit"
        disabled={submitting}
        className="mt-2 rounded-md bg-neutral-900 px-4 py-2 text-white disabled:opacity-50"
      >
        {submitting ? "Generating\u2026" : "Generate design"}
      </button>
    </form>
  );
}
