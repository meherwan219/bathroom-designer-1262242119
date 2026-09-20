"use client";

import type { RecommendationAlternative, SoftScore } from "@/lib/types";

interface Props {
  scores: SoftScore | null;
  alternatives: RecommendationAlternative[];
  onSelectAlternative: (alt: RecommendationAlternative) => void;
}

const LABELS: Record<keyof Omit<SoftScore, "total">, string> = {
  style_match: "Style match",
  feature_coverage: "Feature coverage",
  sustainability: "Sustainability",
  space_efficiency: "Space efficiency",
  family_coherence: "Collection coherence",
  waste_penalty: "Unused budget",
};

/**
 * ScorePanel \u2014 the weighted soft-score breakdown (plan.md's
 * recommendation algorithm) plus up to 2 other ranked itemsets the
 * person can switch to. Never shown as a bare number; always broken
 * into the components that produced it.
 */
export default function ScorePanel({ scores, alternatives, onSelectAlternative }: Props) {
  if (!scores) return null;

  return (
    <div className="flex flex-col gap-4 text-sm">
      <div>
        <p className="mb-1 font-medium">Match score: {Math.round(scores.total * 100)}%</p>
        <div className="flex flex-col gap-1">
          {(Object.keys(LABELS) as (keyof typeof LABELS)[]).map((key) => (
            <div key={key} className="flex items-center gap-2">
              <span className="w-32 shrink-0 text-xs text-neutral-500">{LABELS[key]}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-neutral-200">
                <div
                  className="h-full rounded-full bg-emerald-600"
                  style={{ width: `${Math.min(scores[key] * 100, 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {alternatives.length > 0 && (
        <div>
          <p className="mb-1 font-medium">Other options</p>
          <div className="flex flex-col gap-2">
            {alternatives.map((alt, i) => (
              <button
                key={i}
                onClick={() => onSelectAlternative(alt)}
                className="rounded-md border border-neutral-200 p-2 text-left hover:border-neutral-400"
              >
                <div className="flex justify-between text-xs text-neutral-500">
                  <span>{Math.round(alt.score.total * 100)}% match</span>
                  <span>\u20b9{alt.totals.price_inr.toLocaleString("en-IN")}</span>
                </div>
                <p className="text-xs">
                  {alt.items.filter((it) => it.role.startsWith("primary_")).map((it) => it.name).join(", ")}
                </p>
                {alt.trace.water_savings_pct_vs_baseline !== 0 && (
                  <p className="text-xs text-emerald-600">
                    {alt.trace.water_savings_pct_vs_baseline > 0 ? "\u2193" : "\u2191"}{" "}
                    {Math.abs(alt.trace.water_savings_pct_vs_baseline)}% water use vs. catalog average
                  </p>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
