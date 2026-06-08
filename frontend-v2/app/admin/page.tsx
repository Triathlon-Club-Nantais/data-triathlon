import { PendingProvidersTable } from "@/components/admin/PendingProvidersTable";

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Administration</h1>
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Fournisseurs non supportés signalés</h2>
        <PendingProvidersTable />
      </section>
    </div>
  );
}
