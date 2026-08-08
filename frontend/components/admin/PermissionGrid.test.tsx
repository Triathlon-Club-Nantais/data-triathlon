import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import type { PermissionGroup } from "@/lib/types";

import { PermissionGrid } from "./PermissionGrid";

/**
 * Deux fonctionnalités, dans l'ordre où le serveur les rend — et **pas** dans
 * l'ordre alphabétique, qui placerait « Chronométreurs signalés » en tête. Un
 * tri côté front ferait de l'écran un second lieu où cet ordre se décide.
 */
const INVENTAIRE: PermissionGroup[] = [
  {
    feature: "Rôles et accès",
    permissions: [
      {
        code: "roles:read",
        label: "Consulter les rôles",
        description: "Voir la liste des rôles, leur composition et l'inventaire des pouvoirs.",
      },
      {
        code: "roles:write",
        label: "Composer les rôles",
        description: "Créer, renommer, recomposer et supprimer des rôles.",
      },
    ],
  },
  {
    feature: "Chronométreurs signalés",
    permissions: [
      {
        code: "pending_providers:handle",
        label: "Instruire les signalements",
        description: "Marquer un signalement comme traité et le retirer de la liste.",
      },
    ],
  },
];

function afficher(props: Partial<React.ComponentProps<typeof PermissionGrid>> = {}) {
  return render(
    <PermissionGrid
      groupes={INVENTAIRE}
      coches={new Set(["roles:read"])}
      idPrefixe="r1"
      {...props}
    />,
  );
}

describe("PermissionGrid — lecture", () => {
  it("groupe les pouvoirs par fonctionnalité, dans l'ordre reçu", () => {
    afficher();

    const groupes = screen.getAllByRole("group");
    expect(groupes.map((g) => within(g).getByText(/Rôles et accès|Chronométreurs/).textContent))
      .toEqual(["Rôles et accès", "Chronométreurs signalés"]);
  });

  it("présente chaque pouvoir par son libellé et sa description, jamais par son code seul", () => {
    afficher();

    expect(screen.getByRole("checkbox", { name: /Consulter les rôles/ })).toBeInTheDocument();
    expect(
      screen.getByText("Créer, renommer, recomposer et supprimer des rôles."),
    ).toBeInTheDocument();
    // Le code technique ne s'affiche pas : il ne sert qu'aux attributs.
    expect(screen.queryByText("roles:write")).not.toBeInTheDocument();
  });

  it("reflète la composition du rôle", () => {
    afficher();

    expect(screen.getByRole("checkbox", { name: /Consulter les rôles/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Composer les rôles/ })).not.toBeChecked();
  });

  it("est inerte sans `onToggle` — toutes les cases sont désactivées", () => {
    afficher();

    for (const case_ of screen.getAllByRole("checkbox")) {
      expect(case_).toBeDisabled();
    }
  });

  it("lie chaque case à son étiquette et à sa description", () => {
    afficher();

    const case_ = screen.getByRole("checkbox", { name: /Consulter les rôles/ });
    const decrite = case_.getAttribute("aria-describedby");
    expect(decrite).toBeTruthy();
    expect(document.getElementById(decrite as string)).toHaveTextContent(
      "Voir la liste des rôles",
    );
  });

  it("préfixe les identifiants pour que deux grilles coexistent sans collision", () => {
    const { unmount } = afficher({ idPrefixe: "r1" });
    const premier = screen.getByRole("checkbox", { name: /Consulter les rôles/ }).id;
    unmount();

    afficher({ idPrefixe: "r2" });
    expect(screen.getByRole("checkbox", { name: /Consulter les rôles/ }).id).not.toBe(premier);
  });
});

describe("PermissionGrid — édition et non-amplification", () => {
  it("remonte les bascules quand `onToggle` est fourni", async () => {
    const onToggle = vi.fn();
    afficher({ onToggle });

    await userEvent.click(screen.getByRole("checkbox", { name: /Composer les rôles/ }));
    expect(onToggle).toHaveBeenCalledWith("roles:write", true);

    await userEvent.click(screen.getByRole("checkbox", { name: /Consulter les rôles/ }));
    expect(onToggle).toHaveBeenCalledWith("roles:read", false);
  });

  /**
   * **Figée dans son état, jamais masquée.**
   *
   * `assert_may_grant` exige que la différence **symétrique** avant/après soit
   * couverte par les pouvoirs de l'auteur : ni cocher, ni décocher. Masquer la
   * case ferait mentir l'écran sur la composition du rôle — un Modérateur
   * paraîtrait ne rien porter à qui n'a pas `pending_providers:handle`.
   */
  it("fige une case non détenue dans son état courant, sans la masquer", () => {
    afficher({
      onToggle: vi.fn(),
      coches: new Set(["roles:read", "pending_providers:handle"]),
      disabledCodes: new Set(["pending_providers:handle"]),
      raison: "Vous ne portez pas ce pouvoir.",
    });

    const figee = screen.getByRole("checkbox", { name: /Instruire les signalements/ });
    expect(figee).toBeDisabled();
    expect(figee).toBeChecked();

    // La raison est du texte, lié — pas seulement un `title` que l'œil seul lit.
    const decrite = figee.getAttribute("aria-describedby") ?? "";
    const idRaison = decrite.split(" ").find((id) => id.endsWith("-raison"));
    expect(document.getElementById(idRaison as string)).toHaveTextContent(
      "Vous ne portez pas ce pouvoir.",
    );
  });

  it("laisse basculables les pouvoirs détenus", () => {
    afficher({
      onToggle: vi.fn(),
      disabledCodes: new Set(["pending_providers:handle"]),
      raison: "Vous ne portez pas ce pouvoir.",
    });

    expect(screen.getByRole("checkbox", { name: /Consulter les rôles/ })).toBeEnabled();
    expect(screen.getByRole("checkbox", { name: /Composer les rôles/ })).toBeEnabled();
  });
});
