"use client";

interface Props {
  priceInr: number;
  budgetInr: number;
}

/** ConfigurationRail's "running total vs budget bar" per plan.md's
 * frontend component structure — always visible so the person can see
 * feasibility without reading the BOM line by line. */
export default function BudgetBar({ priceInr, budgetInr }: Props) {
  const pct = budgetInr > 0 ? Math.min((priceInr / budgetInr) * 100, 100) : 0;
  const over = priceInr > budgetInr;

  return (
    <div className="text-sm">
      <div className="mb-1 flex justify-between">
        <span className="font-medium">
          \u20b9{priceInr.toLocaleString("en-IN")} of \u20b9{budgetInr.toLocaleString("en-IN")}
        </span>
        <span className={over ? "text-red-600" : "text-neutral-500"}>
          {over ? "over budget" : `${Math.round(pct)}%`}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-200">
        <div
          className={`h-full rounded-full ${over ? "bg-red-500" : "bg-neutral-900"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
