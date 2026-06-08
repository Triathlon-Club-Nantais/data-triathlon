import { ScrapeForm } from "@/components/scrape/ScrapeForm";

export default function AjouterPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Ajouter un résultat</h1>
      <p className="text-muted-foreground">
        Collez l'URL de chronométrage d'une épreuve. Le résultat de l'athlète est
        prévisualisé, puis tous les participants sont importés en arrière-plan.
      </p>
      <ScrapeForm />
    </div>
  );
}
