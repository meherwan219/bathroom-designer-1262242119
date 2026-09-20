"use client";

import type { BomItem } from "@/lib/types";

interface Props {
  items: BomItem[];
}

/** Bill of materials table — the "catalog facts from API, not LLM
 * prose" ProductDrawer principle from plan.md, in list form. */
export default function Bom({ items }: Props) {
  if (items.length === 0) {
    return <p className="text-sm text-neutral-400">No items selected yet.</p>;
  }
  return (
    <table className="w-full text-sm">
      <tbody>
        {items.map((item) => (
          <tr key={item.sku} className="border-b last:border-0">
            <td className="py-1 pr-2 capitalize text-neutral-500">{item.role.replace("primary_", "")}</td>
            <td className="py-1 pr-2">{item.name}</td>
            <td className="py-1 text-right">\u20b9{item.price_inr.toLocaleString("en-IN")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
