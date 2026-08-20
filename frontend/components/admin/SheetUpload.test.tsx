import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import { ApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import type { SheetColumns } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { readSheetColumns, launchBatchFromFile } = vi.hoisted(() => ({
  readSheetColumns: vi.fn(),
  launchBatchFromFile: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { readSheetColumns, launchBatchFromFile } };
});

import { SheetUpload } from "./SheetUpload";

const COLONNES: SheetColumns = {
  row_count: 128,
  suggested_index: 1,
  columns: [
    { index: 0, header: "Nom", link_count: 0, samples: ["Dupont", "Martin"] },
    {
      index: 1,
      header: "Lien vers les résultats",
      link_count: 117,
      samples: ["https://www.klikego.com/resultats/a"],
    },
  ],
};

const FICHIER = () =>
  new File(["Nom,Lien\n"], "epreuves.csv", { type: "text/csv" });

function afficher() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    qc,
    ...render(
      <QueryClientProvider client={qc}>
        <SheetUpload />
      </QueryClientProvider>,
    ),
  };
}

async function televerser(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText(/fichier/i), FICHIER());
}

beforeEach(() => {
  vi.clearAllMocks();
  readSheetColumns.mockResolvedValue(COLONNES);
  launchBatchFromFile.mockResolvedValue({
    correlation_id: "9ade31c0",
    state: "pending",
    epreuves: 117,
  });
});

describe("SheetUpload", () => {
  it("ne demande la colonne qu'après le téléversement", async () => {
    const user = userEvent.setup();
    afficher();

    expect(screen.queryByLabelText(/colonne/i)).toBeNull();
    await televerser(user);

    expect(await screen.findByLabelText(/colonne/i)).toBeInTheDocument();
  });

  it("présélectionne la colonne la plus fournie", async () => {
    const user = userEvent.setup();
    afficher();

    await televerser(user);

    const selecteur = (await screen.findByLabelText(/colonne/i)) as HTMLSelectElement;
    expect(selecteur.value).toBe("1");
  });

  it("affiche le nombre de liens de chaque colonne", async () => {
    // C'est ce compte qui rend visible une colonne d'hyperliens sans texte :
    // elle en affiche zéro là où on l'attendrait pleine (D8).
    const user = userEvent.setup();
    afficher();

    await televerser(user);

    expect(await screen.findByText(/117 liens/)).toBeInTheDocument();
    expect(screen.getByText(/aucun lien/i)).toBeInTheDocument();
  });

  it("ne présélectionne rien quand aucune colonne ne porte de lien", async () => {
    readSheetColumns.mockResolvedValue({
      ...COLONNES,
      suggested_index: null,
      columns: COLONNES.columns.map((c) => ({ ...c, link_count: 0 })),
    });
    const user = userEvent.setup();
    afficher();

    await televerser(user);

    expect(
      await screen.findByText(/aucune colonne ne semble porter de lien/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /lancer/i })).toBeDisabled();
  });

  it("lance avec la colonne retenue, et renvoie le même fichier", async () => {
    // Le fichier reste dans le navigateur entre les deux appels : il n'est
    // jamais stocké côté serveur (FR-011).
    const user = userEvent.setup();
    afficher();

    await televerser(user);
    await user.click(await screen.findByRole("button", { name: /lancer/i }));

    await waitFor(() => expect(launchBatchFromFile).toHaveBeenCalled());
    const [fichier, colonne, dryRun] = launchBatchFromFile.mock.calls[0];
    expect(fichier.name).toBe("epreuves.csv");
    expect(colonne).toBe(1);
    expect(dryRun).toBe(false);
  });

  it("annonce les épreuves retenues après le lancement", async () => {
    launchBatchFromFile.mockResolvedValue({
      correlation_id: "9ade31c0",
      state: "pending",
      epreuves: 117,
      ignored_by_host: { "chrono-maison.example": 4 },
    });
    const user = userEvent.setup();
    afficher();

    await televerser(user);
    await user.click(await screen.findByRole("button", { name: /lancer/i }));

    expect(await screen.findByText(/117 épreuves/)).toBeInTheDocument();
    // Les liens jamais soumis, dits explicitement : les taire ferait chercher
    // des épreuves manquantes dans le bilan.
    expect(screen.getByText(/chrono-maison\.example/)).toBeInTheDocument();
  });

  it("fait apparaître l'exécution lancée dans la liste des imports", async () => {
    // La plateforme ne rend aucun identifiant au dispatch : c'est l'invalidation
    // qui fait entrer l'exécution dans la liste, où on la retrouve par son
    // `correlation_id`. `useLaunchBatch` le fait pour la reprise en base ; ce
    // chemin-ci l'avait oublié, et l'import lancé restait invisible jusqu'à un
    // rechargement d'onglet (#471).
    const user = userEvent.setup();
    const { qc } = afficher();
    qc.setQueryData(queryKeys.batchRuns(), []);

    await televerser(user);
    await user.click(await screen.findByRole("button", { name: /lancer/i }));

    await waitFor(() =>
      expect(qc.getQueryState(queryKeys.batchRuns())?.isInvalidated).toBe(true),
    );
  });

  it("réaffiche le motif du refus tel qu'il est rendu", async () => {
    const message =
      "Plus de 500 épreuves après dédoublonnage. Découpez le fichier.";
    launchBatchFromFile.mockRejectedValue(new ApiError(422, message));
    const user = userEvent.setup();
    afficher();

    await televerser(user);
    await user.click(await screen.findByRole("button", { name: /lancer/i }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(message));
  });

  it("réaffiche le motif d'un fichier refusé à la lecture", async () => {
    readSheetColumns.mockRejectedValue(
      new ApiError(413, "Fichier trop volumineux : la limite est de 2 Mo."),
    );
    const user = userEvent.setup();
    afficher();

    await televerser(user);

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Fichier trop volumineux : la limite est de 2 Mo.",
      ),
    );
    expect(screen.queryByLabelText(/colonne/i)).toBeNull();
  });
});
