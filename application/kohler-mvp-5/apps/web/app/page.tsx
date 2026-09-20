import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold">KOHLER AI Bathroom Designer</h1>
      <p className="max-w-md text-center text-neutral-600">
        A constraint-first design compiler: chat and form inputs become a
        feasible, catalog-true bathroom layout with a full bill of materials.
      </p>
      <Link
        href="/planner"
        className="rounded-md bg-neutral-900 px-4 py-2 text-white"
      >
        Start planning
      </Link>
    </main>
  );
}
