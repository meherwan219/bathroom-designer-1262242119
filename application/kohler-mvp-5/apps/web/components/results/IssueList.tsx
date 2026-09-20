"use client";

import type { Violation } from "@/lib/types";

interface Props {
  violations: Violation[];
}

/** IssueList: hard violations in red, per plan.md's frontend
 * component structure. Soft misses as suggestions land in Phase 3
 * once soft scoring is real. */
export default function IssueList({ violations }: Props) {
  if (violations.length === 0) {
    return <p className="text-sm text-emerald-600">No hard constraint violations.</p>;
  }
  return (
    <ul className="flex flex-col gap-2">
      {violations.map((v, i) => (
        <li key={i} className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
          <span className="font-mono text-xs text-red-500">{v.code}</span>
          <p>{v.message}</p>
        </li>
      ))}
    </ul>
  );
}
