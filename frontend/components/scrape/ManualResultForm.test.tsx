import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ManualResultForm } from "./ManualResultForm";

function remplirSocle() {
  fireEvent.change(screen.getByLabelText("Prénom"), { target: { value: "Jean" } });
  fireEvent.change(screen.getByLabelText("Nom"), { target: { value: "DUPONT" } });
  fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-05-16" } });
  fireEvent.change(screen.getByLabelText("Nom de l'épreuve"), {
    target: { value: "Triathlon de Nantes" },
  });
}

const submit = () =>
  userEvent.click(screen.getByRole("button", { name: /enregistrer votre participation/i }));

describe("ManualResultForm — champs obligatoires (US1)", () => {
  it("soumission à vide affiche un message sous les quatre champs obligatoires et bloque l'enregistrement", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);

    await submit();

    expect(await screen.findByText("Nom requis")).toBeInTheDocument();
    expect(screen.getByText("Prénom requis")).toBeInTheDocument();
    expect(screen.getByText("Date requise")).toBeInTheDocument();
    expect(screen.getByText("Nom de l'épreuve requis")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("un seul champ manquant (prénom) : seul son message apparaît, l'enregistrement reste bloqué", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Nom"), { target: { value: "DUPONT" } });
    fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-05-16" } });
    fireEvent.change(screen.getByLabelText("Nom de l'épreuve"), {
      target: { value: "Triathlon de Nantes" },
    });
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    await submit();

    expect(await screen.findByText("Prénom requis")).toBeInTheDocument();
    expect(screen.queryByText("Nom requis")).not.toBeInTheDocument();
    expect(screen.queryByText("Date requise")).not.toBeInTheDocument();
    expect(screen.queryByText("Nom de l'épreuve requis")).not.toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("ne propose ni Genre, ni Club, ni Catégorie, et libelle l'épreuve « Nom de l'épreuve »", () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);

    expect(screen.queryByLabelText(/^genre$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^club$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^catégorie$/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Nom de l'épreuve")).toBeInTheDocument();
    expect(screen.queryByLabelText(/^épreuve$/i)).not.toBeInTheDocument();
  });

  it("les quatre champs obligatoires et une discipline suffisent à enregistrer", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);

    remplirSocle();
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    await submit();

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.athlete_firstname).toBe("Jean");
    expect(payload.athlete_name).toBe("DUPONT");
    expect(payload.event_date).toBe("2026-05-16");
    expect(payload.event_name).toBe("Triathlon de Nantes");
  });
});

describe("ManualResultForm — taxonomie FFTri et format (US3)", () => {
  it("propose les huit disciplines demandées", () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    const discipline = screen.getByLabelText("Discipline") as HTMLSelectElement;
    const options = Array.from(discipline.options).map((o) => o.value);
    expect(options).toEqual(
      expect.arrayContaining([
        "triathlon", "duathlon", "swimrun", "bike-run",
        "raid-multisport", "cross-triathlon", "aquathlon", "swim-bike",
      ]),
    );
  });

  it("Triathlon fait apparaître le choix de format", async () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    expect(screen.queryByLabelText(/^Format/)).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    expect(screen.getByLabelText(/^Format/)).toBeInTheDocument();
  });

  it("format « Autre » rend la précision obligatoire et bloque sans elle", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);
    remplirSocle();
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    await userEvent.selectOptions(screen.getByLabelText(/^Format/), "autre");
    await submit();

    expect(await screen.findByText(/précision.*requise/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Précision du format"), {
      target: { value: "Format découverte" },
    });
    await submit();
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].format_label).toBe("Format découverte");
    expect(onSubmit.mock.calls[0][0].event_type).toBe("triathlon");
  });

  it("Raid Multisport n'affiche aucun format mais une distance totale", async () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "raid-multisport");
    expect(screen.queryByLabelText(/^Format/)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/distance totale/i)).toBeInTheDocument();
  });

  it("Swim Bike n'affiche pas de champ de temps de course à pied", async () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "swim-bike");
    expect(screen.queryByLabelText("Course à pied (optionnel)")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Natation (optionnel)")).toBeInTheDocument();
  });

  it("un format normalisé compose le slug, sans précision", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);
    remplirSocle();
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    await userEvent.selectOptions(screen.getByLabelText(/^Format/), "m");
    await submit();

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].event_type).toBe("triathlon-m");
    expect(onSubmit.mock.calls[0][0].format_label).toBe("");
  });
});

describe("ManualResultForm — qualification du résultat (US4)", () => {
  it("individuel est présélectionné", () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    expect(screen.getByRole("radio", { name: "Individuel" })).toBeChecked();
    expect(screen.queryByLabelText("Nom de l'équipe")).not.toBeInTheDocument();
  });

  it("collectif fait apparaître le nom de l'équipe, obligatoire", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);
    remplirSocle();
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    await userEvent.click(screen.getByRole("radio", { name: "Collectif" }));
    expect(screen.getByLabelText("Nom de l'équipe")).toBeInTheDocument();

    await submit();
    expect(await screen.findByText("Nom de l'équipe requis")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("repasser à individuel ne conserve pas le nom d'équipe saisi", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);
    remplirSocle();
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    await userEvent.click(screen.getByRole("radio", { name: "Collectif" }));
    fireEvent.change(screen.getByLabelText("Nom de l'équipe"), {
      target: { value: "Les Foulées" },
    });
    await userEvent.click(screen.getByRole("radio", { name: "Individuel" }));
    await submit();

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].team_name).toBe("");
    expect(onSubmit.mock.calls[0][0].is_relay).toBe(false);
  });

  it("enregistre sans aucun temps renseigné", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);
    remplirSocle();
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    await submit();
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
  });

  it("statut par défaut « Terminée » ; un abandon s'enregistre sans temps ni place", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);
    expect(screen.getByLabelText("Statut")).toHaveValue("finisher");

    remplirSocle();
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    await userEvent.selectOptions(screen.getByLabelText("Statut"), "DNF");
    await submit();

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].status).toBe("DNF");
  });

  it("un lien de vérification saisi est transmis tel quel", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);
    remplirSocle();
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    fireEvent.change(screen.getByLabelText(/lien vers la page de résultats/i), {
      target: { value: "https://club.example/resultats" },
    });
    await submit();

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].evidence_url).toBe("https://club.example/resultats");
  });
});

describe("ManualResultForm — cas limite : changement de discipline après saisie des temps", () => {
  it("un temps de natation saisi puis une discipline sans natation choisie n'est pas transmis", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);
    remplirSocle();
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    fireEvent.change(screen.getByLabelText("Natation (optionnel)"), { target: { value: "00:20:00" } });

    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "bike-run");
    await submit();

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].swim_time).toBe("");
  });
});

describe("ManualResultForm — requis, optionnel et validation au blur (ACT-11)", () => {
  it("marque les cinq champs requis en `aria-required`, et aucun autre", () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);

    for (const nom of ["Prénom", "Nom", "Date", "Nom de l'épreuve", "Discipline"]) {
      expect(screen.getByLabelText(nom)).toHaveAttribute("aria-required", "true");
    }
    expect(screen.getByLabelText(/^Dossard/)).not.toHaveAttribute("aria-required");
    expect(screen.getByLabelText(/^Statut/)).not.toHaveAttribute("aria-required");
  });

  it("suffixe « (optionnel) » aux champs facultatifs", () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);

    expect(screen.getByLabelText("Dossard (optionnel)")).toBeInTheDocument();
    expect(screen.getByLabelText("Place générale (optionnel)")).toBeInTheDocument();
    expect(screen.getByLabelText("Temps total (optionnel)")).toBeInTheDocument();
  });

  it("annonce à quoi sert le lien de résultats, et qu'il est facultatif", () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    expect(
      screen.getByLabelText("Lien vers la page de résultats, si vous en avez un (optionnel)"),
    ).toBeInTheDocument();
  });

  it("valide au blur : quitter Prénom vide affiche son message sans soumettre", async () => {
    const onSubmit = vi.fn();
    render(<ManualResultForm onSubmit={onSubmit} />);

    await userEvent.click(screen.getByLabelText("Prénom"));
    await userEvent.tab();

    expect(await screen.findByText("Prénom requis")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("replie les temps par discipline derrière un dépliant fermé au départ", async () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");

    const depliant = screen.getByText("Ajouter vos temps par discipline").closest("details");
    expect(depliant).not.toBeNull();
    expect(depliant).not.toHaveAttribute("open");
    // Le temps total, lui, reste visible sans dépliage.
    expect(screen.getByLabelText("Temps total (optionnel)").closest("details")).toBeNull();
  });

  it("légende l'astérisque plutôt que de supposer la convention connue", () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    expect(screen.getByText(/Les champs marqués .*sont obligatoires/)).toBeInTheDocument();
  });

  it("marque aussi les temps par discipline comme optionnels", async () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    expect(screen.getByLabelText("Natation (optionnel)")).toBeInTheDocument();
  });

  it("garde le vouvoiement jusque dans le dépliant des temps", async () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    expect(screen.getByText("Ajouter vos temps par discipline")).toBeInTheDocument();
  });

  it("regroupe la saisie en Qui / Quelle épreuve / Quel résultat / Temps", () => {
    render(<ManualResultForm onSubmit={vi.fn()} />);
    for (const groupe of ["Qui", "Quelle épreuve", "Quel résultat", "Temps"]) {
      expect(screen.getByRole("group", { name: groupe })).toBeInTheDocument();
    }
  });
});
