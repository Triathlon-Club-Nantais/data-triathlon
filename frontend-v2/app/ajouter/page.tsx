import { PageHeader } from "@/components/layout/PageHeader";
import { ScrapeForm } from "@/components/scrape/ScrapeForm";

export default function AjouterPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Ajouter un résultat"
        description="Collez l'URL de chronométrage d'une épreuve : tous les participants sont importés en arrière-plan. Pour un fournisseur non supporté, utilisez la saisie manuelle."
      />
      <ScrapeForm />
    </div>
  );
}
