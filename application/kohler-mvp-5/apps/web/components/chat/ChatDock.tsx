"use client";

import { useState, type FormEvent } from "react";
import type { ChatAlternative, ChatMessage } from "@/lib/types";

interface Props {
  messages: ChatMessage[];
  alternatives: ChatAlternative[];
  onSend: (message: string) => void;
  onApplyAlternative: (alt: ChatAlternative) => void;
  disabled: boolean;
}

/**
 * ChatDock — conversational modify + explanations (plan.md Phase 2).
 * Disabled with a note until a design has been generated once, since
 * chat modifies an existing spec rather than creating one.
 */
export default function ChatDock({ messages, alternatives, onSend, onApplyAlternative, disabled }: Props) {
  const [draft, setDraft] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!draft.trim() || disabled) return;
    onSend(draft.trim());
    setDraft("");
  }

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex-1 space-y-2 overflow-y-auto">
        {messages.length === 0 && (
          <p className="text-sm text-neutral-400">
            {disabled
              ? "Generate a design first, then ask for changes here \u2014 e.g. \u201clower the budget to 250000\u201d."
              : "Ask for a change, e.g. \u201clower the budget to 250000\u201d."}
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
              m.role === "user"
                ? "ml-auto bg-neutral-900 text-white"
                : "bg-neutral-100 text-neutral-800"
            }`}
          >
            {m.text}
          </div>
        ))}
        {alternatives.length > 0 && (
          <div className="flex flex-col gap-1 rounded-lg border border-amber-200 bg-amber-50 p-2 text-sm">
            <p className="font-medium text-amber-800">That wasn't feasible. Try instead:</p>
            {alternatives.map((alt, i) => (
              <button
                key={i}
                onClick={() => onApplyAlternative(alt)}
                className="rounded border border-amber-300 bg-white px-2 py-1 text-left text-amber-900 hover:bg-amber-100"
              >
                {alt.description}
                {alt.would_be_feasible ? " \u2713" : " (still infeasible)"}
              </button>
            ))}
          </div>
        )}
      </div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={disabled}
          placeholder={disabled ? "Generate a design first\u2026" : "Ask for a change\u2026"}
          className="flex-1 rounded border px-2 py-1 text-sm disabled:bg-neutral-100"
        />
        <button
          type="submit"
          disabled={disabled}
          className="rounded bg-neutral-900 px-3 py-1 text-sm text-white disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  );
}
