import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

import { DangerConfirm, DangerConfirmProvider, useDangerConfirm } from "./DangerConfirm";

describe("DangerConfirm", () => {
  it("rend le titre et le libellé d'action demandés", () => {
    render(
      <DangerConfirm open onOpenChange={vi.fn()} titre="Retirer « a@b.fr » ?" libelleAction="Retirer" onConfirm={vi.fn()} />,
    );
    expect(screen.getByText("Retirer « a@b.fr » ?")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retirer" })).toBeTruthy();
  });

  it("agit au clic quand aucun mot n'est exigé", async () => {
    const onConfirm = vi.fn();
    render(<DangerConfirm open onOpenChange={vi.fn()} titre="Supprimer ?" onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole("button", { name: "Supprimer définitivement" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("garde l'action inerte tant que le mot exigé n'est pas tapé", async () => {
    const onConfirm = vi.fn();
    render(
      <DangerConfirm open onOpenChange={vi.fn()} titre="Purger ?" motDeConfirmation="SUPPRIMER" onConfirm={onConfirm} />,
    );
    const action = screen.getByRole("button", { name: "Supprimer définitivement" });
    expect(action.hasAttribute("disabled")).toBe(true);

    await userEvent.type(screen.getByLabelText(/Tapez/), "SUPPRIM");
    expect(action.hasAttribute("disabled")).toBe(true);

    await userEvent.type(screen.getByLabelText(/Tapez/), "ER");
    expect(action.hasAttribute("disabled")).toBe(false);
    await userEvent.click(action);
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("garde l'action inerte tant que `actionBloquee` vaut vrai, mot tapé ou non", () => {
    render(<DangerConfirm open onOpenChange={vi.fn()} titre="Purger ?" actionBloquee onConfirm={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Supprimer définitivement" }).hasAttribute("disabled")).toBe(true);
  });

  it("ne propose pas de taper le mot tant que l'action reste bloquée", () => {
    render(
      <DangerConfirm
        open
        onOpenChange={vi.fn()}
        titre="Purger ?"
        motDeConfirmation="SUPPRIMER"
        actionBloquee
        onConfirm={vi.fn()}
      />,
    );
    // Un message dit que rien ne se passera (`actionBloquee`) : proposer de
    // taper un mot en dessous serait bavard pour rien.
    expect(screen.queryByLabelText(/Tapez/)).not.toBeInTheDocument();
  });

  it("ferme sans agir sur « Renoncer »", async () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(<DangerConfirm open onOpenChange={onOpenChange} titre="Supprimer ?" onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("oublie la saisie entre deux ouvertures", async () => {
    const { rerender } = render(
      <DangerConfirm open onOpenChange={vi.fn()} titre="Purger ?" motDeConfirmation="SUPPRIMER" onConfirm={vi.fn()} />,
    );
    await userEvent.type(screen.getByLabelText(/Tapez/), "SUPPRIMER");
    rerender(
      <DangerConfirm open={false} onOpenChange={vi.fn()} titre="Purger ?" motDeConfirmation="SUPPRIMER" onConfirm={vi.fn()} />,
    );
    rerender(
      <DangerConfirm open onOpenChange={vi.fn()} titre="Purger ?" motDeConfirmation="SUPPRIMER" onConfirm={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Supprimer définitivement" }).hasAttribute("disabled")).toBe(true);
  });

  it("affiche l'avertissement et le corps chiffré qu'on lui passe", () => {
    render(
      <DangerConfirm open onOpenChange={vi.fn()} titre="Retirer ?" avertissement="Ce rôle est le vôtre." onConfirm={vi.fn()}>
        <p>12 résultats seront détruits.</p>
      </DangerConfirm>,
    );
    expect(screen.getByText("Ce rôle est le vôtre.")).toBeTruthy();
    expect(screen.getByText("12 résultats seront détruits.")).toBeTruthy();
  });
});

describe("useDangerConfirm", () => {
  function Cobaye({ journal }: { journal: (verdict: boolean) => void }) {
    const confirmer = useDangerConfirm();
    return (
      <button
        type="button"
        onClick={async () => journal(await confirmer({ titre: "Retirer « a@b.fr » ?", libelleAction: "Retirer" }))}
      >
        Déclencher
      </button>
    );
  }

  function afficher(journal: (verdict: boolean) => void) {
    return render(
      <DangerConfirmProvider>
        <Cobaye journal={journal} />
      </DangerConfirmProvider>,
    );
  }

  it("résout `true` quand on confirme", async () => {
    const journal = vi.fn();
    afficher(journal);
    await userEvent.click(screen.getByRole("button", { name: "Déclencher" }));
    await userEvent.click(screen.getByRole("button", { name: "Retirer" }));
    await waitFor(() => expect(journal).toHaveBeenCalledWith(true));
  });

  it("résout `false` quand on renonce", async () => {
    const journal = vi.fn();
    afficher(journal);
    await userEvent.click(screen.getByRole("button", { name: "Déclencher" }));
    await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
    await waitFor(() => expect(journal).toHaveBeenCalledWith(false));
  });

  it("refuse de servir hors de son provider", () => {
    // Sans le provider, le geste s'exécuterait sans confirmation : mieux vaut
    // un écran cassé au premier rendu qu'une destruction silencieuse.
    const muet = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Cobaye journal={vi.fn()} />)).toThrow(/DangerConfirmProvider/);
    muet.mockRestore();
  });
});
