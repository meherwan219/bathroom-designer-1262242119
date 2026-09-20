export default function DesignPage({ params }: { params: { id: string } }) {
  return (
    <main className="p-8">
      <h1 className="text-xl font-semibold">Design {params.id}</h1>
      <p className="text-sm text-neutral-500">
        Read-only shared/loaded design view — Phase 1.
      </p>
    </main>
  );
}
