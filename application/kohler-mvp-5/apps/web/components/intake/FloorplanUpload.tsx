"use client";

import { useState, type ChangeEvent } from "react";
import { api } from "@/lib/api";
import type { FloorplanProposal } from "@/lib/types";

interface Props {
  onConfirm: (widthMm: number, depthMm: number) => void;
}

/**
 * Optional floor-plan photo upload \u2014 per plan.md: "User confirms
 * dimensions in UI. Never auto-trust pixels for hard constraints."
 * The proposal is shown as an editable draft; onConfirm only fires
 * when the user explicitly clicks "Use these dimensions," and even
 * then only width/depth reach the intake form \u2014 nothing here calls
 * a design API directly. Door candidates are shown for reference but
 * not yet wired into the intake form (documented scope boundary, not
 * silently dropped).
 */
export default function FloorplanUpload({ onConfirm }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<FloorplanProposal | null>(null);
  const [draftWidth, setDraftWidth] = useState(0);
  const [draftDepth, setDraftDepth] = useState(0);

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    setProposal(null);

    try {
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve((reader.result as string).split(",")[1]);
        reader.onerror = () => reject(new Error("Could not read the image file."));
        reader.readAsDataURL(file);
      });

      const res = await api.extractFloorplan(base64);
      if (res.error || !res.proposal) {
        setError(res.error ?? "Couldn't read dimensions from that image.");
        return;
      }
      setProposal(res.proposal);
      setDraftWidth(res.proposal.width_mm);
      setDraftDepth(res.proposal.depth_mm);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-dashed border-neutral-300 p-3 text-sm">
      <label className="font-medium">Or upload a floor-plan photo</label>
      <input type="file" accept="image/*" onChange={handleFile} disabled={loading} className="text-xs" />
      {loading && <p className="text-xs text-neutral-400">Reading image\u2026</p>}
      {error && <p className="text-xs text-red-600">{error}</p>}

      {proposal && (
        <div className="mt-1 flex flex-col gap-2 rounded border border-amber-200 bg-amber-50 p-2">
          <p className="text-xs text-amber-800">
            Draft read at {Math.round(proposal.confidence * 100)}% confidence \u2014 check and adjust
            before using.
          </p>
          <div className="flex gap-2">
            <label className="flex flex-col text-xs">
              Width (mm)
              <input
                type="number"
                value={draftWidth}
                onChange={(e) => setDraftWidth(Number(e.target.value))}
                className="w-24 rounded border px-1 py-0.5"
              />
            </label>
            <label className="flex flex-col text-xs">
              Depth (mm)
              <input
                type="number"
                value={draftDepth}
                onChange={(e) => setDraftDepth(Number(e.target.value))}
                className="w-24 rounded border px-1 py-0.5"
              />
            </label>
          </div>
          {proposal.doors && proposal.doors.length > 0 && (
            <p className="text-xs text-neutral-500">
              Detected {proposal.doors.length} door{proposal.doors.length > 1 ? "s" : ""} (not yet
              editable here \u2014 add manually if needed).
            </p>
          )}
          <button
            type="button"
            onClick={() => onConfirm(draftWidth, draftDepth)}
            className="self-start rounded bg-amber-700 px-2 py-1 text-xs text-white"
          >
            Use these dimensions
          </button>
        </div>
      )}
    </div>
  );
}
