"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type {
  ChatAlternative,
  ChatMessage,
  ConfigFlags,
  DesignSpecPayload,
  GenerateResponse,
  RecommendationAlternative,
} from "@/lib/types";
import IntakePanel from "@/components/intake/IntakePanel";
import Canvas2D from "@/components/canvas2d/Canvas2D";
import Canvas3D from "@/components/canvas3d/Canvas3D";
import BudgetBar from "@/components/results/BudgetBar";
import IssueList from "@/components/results/IssueList";
import Bom from "@/components/results/Bom";
import ScorePanel from "@/components/results/ScorePanel";
import ChatDock from "@/components/chat/ChatDock";

/**
 * Planner workspace.
 *
 * Phase 1: Intake -> POST /designs -> POST /designs/{id}/generate ->
 * Canvas2D + BudgetBar + IssueList + Bom.
 * Phase 2: ChatDock -> POST /designs/{id}/chat -> same panels update,
 * plus repair-alternative chips when a chat edit isn't feasible.
 * Phase 3: ScorePanel -> soft-score breakdown + selectable
 * recommendation alternatives.
 * Phase 4: CanvasStage toggles 2D/3D (3D only rendered when
 * ENABLE_3D and a valid layout_ir exist, per plan.md); optional
 * floor-plan photo upload inside IntakePanel, gated on ENABLE_VISION.
 */
export default function PlannerPage() {
  const [config, setConfig] = useState<ConfigFlags | null>(null);
  const [viewMode, setViewMode] = useState<"2d" | "3d">("2d");

  const [designId, setDesignId] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [alternatives, setAlternatives] = useState<ChatAlternative[]>([]);
  const [chatBusy, setChatBusy] = useState(false);

  useEffect(() => {
    api.config().then(setConfig).catch(() => setConfig({ enable_3d: false, enable_vision: false }));
  }, []);

  async function handleGenerate(spec: DesignSpecPayload) {
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createDesign(spec);
      setDesignId(created.id);
      const generated = await api.generateDesign(created.id);
      setResult(generated);
      setMessages([]);
      setAlternatives([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  async function sendChat(message: string) {
    if (!designId) return;
    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setChatBusy(true);
    try {
      const res = await api.chatModify(designId, message);
      setMessages((prev) => [...prev, { role: "assistant", text: res.reply }]);
      setAlternatives(res.alternatives);
      setResult({
        spec: res.spec,
        layout_ir: res.layout_ir,
        items: res.items,
        totals: res.totals,
        hard_violations: res.hard_violations,
        soft_scores: null,
        explanation: res.reply,
        recommendation_alternatives: [],
      });
    } catch (err) {
      const text = err instanceof Error ? err.message : "Something went wrong.";
      setMessages((prev) => [...prev, { role: "assistant", text }]);
    } finally {
      setChatBusy(false);
    }
  }

  function applyAlternative(alt: ChatAlternative) {
    const summary = `Apply: ${alt.description}`;
    void sendChat(summary);
  }

  async function selectRecommendation(alt: RecommendationAlternative) {
    if (!designId) return;
    try {
      const switched = await api.selectAlternative(designId, alt.rank);
      setResult(switched);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't switch to that option.");
    }
  }

  const hasLayout = result && result.layout_ir && "objects" in result.layout_ir;
  const show3dToggle = Boolean(config?.enable_3d) && hasLayout;

  return (
    <main className="grid h-screen grid-cols-[320px_1fr_320px] grid-rows-[1fr_auto]">
      <aside className="row-span-2 overflow-y-auto border-r p-4">
        <h2 className="mb-2 text-sm font-semibold uppercase text-neutral-500">Intake</h2>
        <IntakePanel
          onSubmit={handleGenerate}
          submitting={submitting}
          enableVision={Boolean(config?.enable_vision)}
        />
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </aside>

      <section className="relative flex flex-col border-b p-4">
        {show3dToggle && (
          <div className="mb-2 flex gap-1 self-end">
            {(["2d", "3d"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`rounded px-2 py-1 text-xs uppercase ${
                  viewMode === mode ? "bg-neutral-900 text-white" : "bg-neutral-100 text-neutral-500"
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        )}
        <div className="flex flex-1 items-center justify-center">
          {hasLayout ? (
            viewMode === "3d" && show3dToggle ? (
              <Canvas3D layoutIr={result!.layout_ir as never} />
            ) : (
              <Canvas2D layoutIr={result!.layout_ir as never} />
            )
          ) : (
            <p className="text-sm text-neutral-400">
              {submitting
                ? "Solving\u2026"
                : "Fill in the intake form and generate a design to see the plan."}
            </p>
          )}
        </div>
      </section>

      <aside className="row-span-2 flex flex-col gap-6 overflow-y-auto border-l p-4">
        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase text-neutral-500">Budget</h2>
          {result ? (
            <BudgetBar priceInr={result.totals.price_inr} budgetInr={result.totals.budget_inr} />
          ) : (
            <p className="text-sm text-neutral-400">No design generated yet.</p>
          )}
        </div>
        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase text-neutral-500">Bill of materials</h2>
          <Bom items={result?.items ?? []} />
        </div>
        {result && (
          <div>
            <h2 className="mb-2 text-sm font-semibold uppercase text-neutral-500">Match &amp; options</h2>
            <ScorePanel
              scores={result.soft_scores}
              alternatives={result.recommendation_alternatives}
              onSelectAlternative={selectRecommendation}
            />
          </div>
        )}
        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase text-neutral-500">Issues</h2>
          <IssueList violations={result?.hard_violations ?? []} />
        </div>
      </aside>

      <section className="border-t p-4" style={{ height: 220 }}>
        <h2 className="mb-2 text-sm font-semibold uppercase text-neutral-500">Chat</h2>
        <div style={{ height: 160 }}>
          <ChatDock
            messages={messages}
            alternatives={alternatives}
            onSend={sendChat}
            onApplyAlternative={applyAlternative}
            disabled={!designId || chatBusy}
          />
        </div>
      </section>
    </main>
  );
}
