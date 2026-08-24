import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import { DangerConfirmProvider } from "./DangerConfirm";
import type { PermissionGroup, Role, SessionUser } from "@/lib/types";

const { listPermissions, listRoles, getSession, createRole, updateRole, deleteRole } = vi.hoisted(
  () => ({
    listPermissions: vi.fn(),
    listRoles: vi.fn(),
    getSession: vi.fn(),
    createRole: vi.fn(),
    updateRole: vi.fn(),
    deleteRole: vi.fn(),
  }),
);

const { toastError, toastSuccess } = vi.hoisted(() => ({
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listPermissions, listRoles, getSession, createRole, updateRole, deleteRole },
  };
});

import { RolePermissionsEditor } from "./RolePermissionsEditor";

const INVENTAIRE: PermissionGroup[] = [
  {
    feature: "Rôles et accès",
    permissions: [
      {
        code: "roles:read",
        label: "Consulter les rôles",
        description: "Voir la liste des rôles et leur composition.",
      },
      {
        code: "roles:write",
        label: "Composer les rôles",
        description: "Créer, renommer, recomposer et supprimer des rôles.",
      },
    ],
  },
  {
    feature: "Qualité des données",
    permissions: [
      {
        code: "quality:override",
        label: "Trancher la fiabilité",
        description: "Déclarer à la main qu'une épreuve est fiable ou douteuse.",
      },
    ],
  },
];

const ADMIN: Role = {
  id: 1,
  organisation_id: null,
  slug: "admin",
  name: "Administrateur",
  description: "Franchit tout pouvoir, y compris ceux livrés après lui.",
  is_system: true,
  is_superuser: true,
  // Non vide **exprès** : un rôle superutilisateur garde sa composition
  // enregistrée. Avec une liste vide, « aucune case n'est cochée » passerait sur
  // n'importe quel rendu, y compris un composant qui ne rend rien.
  permissions: ["roles:read"],
  stale_permissions: [],
  holders: 2,
};

const VALIDATOR: Role = {
  id: 2,
  organisation_id: null,
  slug: "validator",
  name: "Validateur",
  description: "Tranche la fiabilité des épreuves douteuses.",
  is_system: true,
  is_superuser: false,
  permissions: ["quality:override"],
  stale_permissions: [],
  holders: 0,
};

const BENEVOLE: Role = {
  id: 3,
  organisation_id: null,
  slug: "benevole",
  name: "Bénévole",
  description: "",
  is_system: false,
  is_superuser: false,
  permissions: ["roles:read"],
  stale_permissions: ["legacy:oldpower"],
  holders: 0,
};

/** Une session superutilisatrice : elle porte le rôle `admin`, qui l'est. */
const SESSION: SessionUser = {
  id: 1,
  email: "admin@exemple.fr",
  display_name: "Camille",
  created_at: "2026-08-01T14:54:28Z",
  permissions: ["roles:read", "roles:write", "quality:override"],
  roles: [{ id: ADMIN.id, slug: "admin", name: "Administrateur", organisation_id: null }],
  groups: [],
};

/** `null` = visiteur anonyme (401, qui n'est pas une panne) ; une `Error` = panne réelle. */
function afficher(session: SessionUser | null | Error = SESSION) {
  if (session instanceof Error) getSession.mockRejectedValue(session);
  else if (session) getSession.mockResolvedValue(session);
  else getSession.mockRejectedValue(new ApiError(401, "anonyme"));

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <RolePermissionsEditor />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

/** Déplie le panneau d'un rôle et rend son contenu. */
async function ouvrir(nom: string) {
  await userEvent.click(await screen.findByRole("button", { name: new RegExp(nom) }));
  return screen.getByRole("region", { name: new RegExp(nom) });
}

/** Vise le bouton du dialog plutôt que celui du panneau : les deux partagent
 *  parfois le même libellé, mais seul le premier vit dans `role="dialog"`. */
async function confirmerDansLeDialog(nom: RegExp | string) {
  const dialog = await screen.findByRole("dialog");
  await userEvent.click(within(dialog).getByRole("button", { name: nom }));
}

beforeEach(() => {
  // `mockReset` avant de réarmer : sans lui, les compteurs d'appels et les
  // `mockResolvedValueOnce` d'un test fuient dans le suivant.
  listPermissions.mockReset();
  listRoles.mockReset();
  getSession.mockReset();
  listPermissions.mockResolvedValue(INVENTAIRE);
  listRoles.mockResolvedValue([ADMIN, VALIDATOR, BENEVOLE]);
  updateRole.mockReset();
  createRole.mockReset();
  deleteRole.mockReset();
  toastError.mockReset();
  toastSuccess.mockReset();
});

describe("RolePermissionsEditor — lecture", () => {
  it("liste les rôles avec leur nom, leur description et leur nombre de porteurs", async () => {
    afficher();

    expect(await screen.findByRole("button", { name: /Administrateur/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Administrateur/ })).toHaveTextContent(
      "2 porteurs",
    );
    expect(screen.getByRole("button", { name: /Validateur/ })).toHaveTextContent("0 porteur");

    const panneau = await ouvrir("Validateur");
    expect(within(panneau).getByLabelText(/description/i)).toHaveValue(
      "Tranche la fiabilité des épreuves douteuses.",
    );
  });

  it("ne souligne au survol que le nom du rôle, ni ses badges ni son décompte", async () => {
    // La primitive porte `hover:underline` sur un déclencheur en `flex-1` : le
    // trait courait sur toute la largeur de la ligne (#324). On ne réduit que
    // le trait, jamais la cible cliquable.
    afficher();

    const ligne = await screen.findByRole("button", { name: /Administrateur/ });
    expect(ligne).not.toHaveClass("hover:underline");
    expect(ligne).toHaveClass("flex-1");
    // Le trait pleine largeur tenait aussi lieu d'affordance. En le réduisant au
    // nom, il fallait le second indice qui manquait : Tailwind v4 ne pose plus
    // de `cursor` sur `button` (rien dans son preflight, rien dans globals.css),
    // donc la ligne se survolait à la flèche.
    expect(ligne).toHaveClass("cursor-pointer");
    expect(screen.getByText("Administrateur")).toHaveClass(
      "group-hover/accordion-trigger:underline",
    );
    // Le nom du groupe est le **contrat** avec la primitive, et c'est la seule
    // pièce dont ce correctif dépende : `components/ui/` est une copie shadcn
    // re-synchronisable, donc un renommage en amont est réaliste. Sans cette
    // ligne, il laisse la suite verte et le soulignement mort.
    expect(ligne).toHaveClass("group/accordion-trigger");
    // Deuxième case de #324, affirmée de front plutôt que déduite. Restreint à
    // la ligne visée : deux rôles de la fixture sont `is_system`, donc deux
    // badges « livré » cohabitent à l'écran.
    expect(within(ligne).getByText("livré")).not.toHaveClass(
      "group-hover/accordion-trigger:underline",
    );
    expect(within(ligne).getByText("2 porteurs")).not.toHaveClass(
      "group-hover/accordion-trigger:underline",
    );
  });

  it("groupe les pouvoirs par fonctionnalité, avec libellé et description en français", async () => {
    afficher();
    const panneau = await ouvrir("Validateur");

    expect(within(panneau).getByRole("group", { name: "Rôles et accès" })).toBeInTheDocument();
    expect(
      within(panneau).getByRole("group", { name: "Qualité des données" }),
    ).toBeInTheDocument();
    expect(
      within(panneau).getByRole("checkbox", { name: /Trancher la fiabilité/ }),
    ).toBeChecked();
  });

  /**
   * **Le statut n'est pas dix-huit cases cochées.**
   *
   * `effective_permissions` court-circuite l'inventaire sur un
   * superutilisateur, et `has_permission` court-circuite avant même lui : un
   * pouvoir livré demain est franchi demain. Cocher les cases d'aujourd'hui
   * dirait « ces dix-huit-là », soit exactement le contresens.
   */
  it("présente `is_superuser` comme un statut, pas comme des cases cochées", async () => {
    afficher();
    const panneau = await ouvrir("Administrateur");

    // La phrase de statut, et non la description du rôle — qui dit déjà
    // « franchit tout pouvoir » et rendrait l'assertion complaisante.
    expect(within(panneau).getByText(/Superutilisateur/)).toBeInTheDocument();
    expect(within(panneau).getByText(/ne décide de rien/i)).toBeInTheDocument();
    // Sa composition enregistrée reste **affichée** — c'est ce que dit la phrase
    // de statut — mais elle est inerte : aucune case ne se coche ni ne se décoche.
    expect(within(panneau).getByRole("checkbox", { name: /Consulter les rôles/ })).toBeChecked();
    expect(
      within(panneau).getByRole("checkbox", { name: /Trancher la fiabilité/ }),
    ).not.toBeChecked();
    for (const case_ of within(panneau).getAllByRole("checkbox")) {
      expect(case_).toBeDisabled();
    }
  });

  it("montre les codes périmés à part, annoncés sans effet", async () => {
    afficher();
    const panneau = await ouvrir("Bénévole");

    const perimes = within(panneau).getByRole("group", { name: /périmé/i });
    expect(within(perimes).getByText("legacy:oldpower")).toBeInTheDocument();
    expect(perimes).toHaveTextContent(/sans effet/i);
    // Distinct de l'inventaire : le code périmé n'est pas une case de la grille.
    expect(
      within(panneau).queryByRole("checkbox", { name: /legacy:oldpower/ }),
    ).not.toBeInTheDocument();
  });

  it.each([
    { statut: 403, titre: /accès refusé/i },
    { statut: 401, titre: /session expirée/i },
  ])("dit « $titre » sur un $statut, jamais une liste vide", async ({ statut, titre }) => {
    listRoles.mockRejectedValue(new ApiError(statut, "refus"));

    afficher();

    expect(await screen.findByText(titre)).toBeInTheDocument();
    expect(screen.queryByText(/aucun rôle/i)).not.toBeInTheDocument();
  });
});

describe("RolePermissionsEditor — recomposition", () => {
  /**
   * **Renommer n'est pas recomposer.**
   *
   * `permissions` **remplace** l'ensemble côté serveur. L'envoyer à chaque
   * enregistrement transformerait toute correction de libellé en purge
   * silencieuse des codes périmés du rôle.
   */
  it("n'envoie que le nom quand seul le nom a changé", async () => {
    updateRole.mockResolvedValue({ ...VALIDATOR, name: "Validateur qualité" });
    afficher();
    const panneau = await ouvrir("Validateur");

    const nom = within(panneau).getByLabelText(/nom du rôle/i);
    await userEvent.clear(nom);
    await userEvent.type(nom, "Validateur qualité");
    await userEvent.click(within(panneau).getByRole("button", { name: "Enregistrer" }));

    expect(updateRole).toHaveBeenCalledWith(VALIDATOR.id, { name: "Validateur qualité" });
  });

  it("envoie l'ensemble complet des codes quand la composition change", async () => {
    updateRole.mockResolvedValue(VALIDATOR);
    afficher();
    const panneau = await ouvrir("Validateur");

    await userEvent.click(
      within(panneau).getByRole("checkbox", { name: /Consulter les rôles/ }),
    );
    await userEvent.click(within(panneau).getByRole("button", { name: "Enregistrer" }));

    expect(updateRole).toHaveBeenCalledWith(VALIDATOR.id, {
      permissions: expect.arrayContaining(["quality:override", "roles:read"]),
    });
    expect(updateRole.mock.calls[0][1].permissions).toHaveLength(2);
  });

  /**
   * Un rôle livré avec l'application reste modifiable — « livré ne veut pas
   * dire figé » (`authorization.update_role`). Seule sa suppression est
   * refusée. L'énoncé de #240 disait l'inverse ; les trois rôles de
   * l'installation étant tous livrés, le suivre gèlerait l'écran au premier jour.
   */
  it("laisse renommer et recomposer un rôle livré avec l'application", async () => {
    updateRole.mockResolvedValue(VALIDATOR);
    afficher();
    const panneau = await ouvrir("Validateur");

    expect(within(panneau).getByLabelText(/nom du rôle/i)).toBeEnabled();
    expect(
      within(panneau).getByRole("checkbox", { name: /Consulter les rôles/ }),
    ).toBeEnabled();
  });

  /** Le slug traverse `grant-role --role` et le semis : il est fixé à la création. */
  it("n'expose aucun champ d'identifiant en modification", async () => {
    afficher();
    const panneau = await ouvrir("Validateur");

    expect(within(panneau).queryByLabelText(/identifiant/i)).not.toBeInTheDocument();
    expect(within(panneau).queryByDisplayValue("validator")).not.toBeInTheDocument();
  });

  it("prévient que l'enregistrement emporte les codes périmés, avant de valider", async () => {
    updateRole.mockResolvedValue(BENEVOLE);
    afficher();
    const panneau = await ouvrir("Bénévole");

    // Tant que la composition n'a pas bougé, rien n'est purgé, donc rien n'est annoncé.
    expect(within(panneau).queryByText(/disparaîtr/i)).not.toBeInTheDocument();

    await userEvent.click(
      within(panneau).getByRole("checkbox", { name: /Composer les rôles/ }),
    );
    expect(within(panneau).getByText(/disparaîtr/i)).toHaveTextContent("legacy:oldpower");

    await userEvent.click(within(panneau).getByRole("button", { name: "Enregistrer" }));
    expect(updateRole.mock.calls[0][1].permissions).not.toContain("legacy:oldpower");
  });

  /**
   * FR-016 — un code périmé est retirable par **tout le monde**.
   *
   * `assert_may_grant` intersecte avec l'inventaire : un code absent de
   * l'inventaire n'est jamais visé par la non-amplification. Sans cela, un rôle
   * qui en traîne un deviendrait immodifiable pour tous, et `is_system` ou
   * attribué, indélébile — un nettoyage de code ordinaire suffirait à le geler.
   */
  it("laisse une session aux pouvoirs limités purger un code périmé", async () => {
    updateRole.mockResolvedValue(BENEVOLE);
    // Cette session ne porte que de quoi composer, et rien d'autre.
    afficher({ ...SESSION, permissions: ["roles:write"], roles: [] });
    const panneau = await ouvrir("Bénévole");

    expect(within(panneau).getByRole("checkbox", { name: /Consulter les rôles/ })).toBeDisabled();
    expect(within(panneau).getByRole("checkbox", { name: /Trancher la fiabilité/ })).toBeDisabled();
    // Et pourtant la purge reste offerte : elle ne passe par aucune case.
    await userEvent.click(within(panneau).getByRole("button", { name: /purger/i }));
    await userEvent.click(within(panneau).getByRole("button", { name: "Enregistrer" }));

    expect(updateRole).toHaveBeenCalledWith(BENEVOLE.id, { permissions: ["roles:read"] });
  });

  it("rend le message du serveur tel quel et retombe sur son état", async () => {
    updateRole.mockRejectedValue(
      new ApiError(409, "Cette opération laisserait l'installation sans aucun administrateur."),
    );
    afficher();
    const panneau = await ouvrir("Validateur");

    const nom = within(panneau).getByLabelText(/nom du rôle/i);
    await userEvent.clear(nom);
    await userEvent.type(nom, "Autre nom");
    await userEvent.click(within(panneau).getByRole("button", { name: "Enregistrer" }));

    await vi.waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Cette opération laisserait l'installation sans aucun administrateur.",
      ),
    );
    // L'affichage retombe sur ce que le serveur porte, pas sur ce qu'on a tenté.
    await vi.waitFor(() =>
      expect(within(panneau).getByLabelText(/nom du rôle/i)).toHaveValue("Validateur"),
    );
  });
});

describe("RolePermissionsEditor — statut de superutilisateur", () => {
  it("propose la bascule à une session qui porte un rôle superutilisateur", async () => {
    afficher();
    const panneau = await ouvrir("Validateur");

    expect(
      within(panneau).getByRole("button", { name: /superutilisateur/i }),
    ).toBeInTheDocument();
  });

  /**
   * **La déduction est exacte, elle n'est pas une inférence.**
   *
   * `GET /auth/me` ne rend pas `is_superuser` ; c'est le croisement des rôles
   * portés avec la liste déjà chargée qui répond, exactement comme
   * `authorization._is_superuser`. Déduire le statut de « il porte tous les
   * codes » serait faux : un rôle ordinaire cochant toutes les cases produit la
   * même liste sans franchir les pouvoirs à venir — et
   * `assert_may_set_superuser` répondrait 403 sur une bascule qu'on aurait
   * offerte.
   */
  it("ne la propose pas à qui porte tous les codes sans porter un rôle superutilisateur", async () => {
    afficher({
      ...SESSION,
      permissions: ["roles:read", "roles:write", "quality:override"],
      roles: [{ id: VALIDATOR.id, slug: "validator", name: "Validateur", organisation_id: null }],
    });
    const panneau = await ouvrir("Bénévole");

    expect(
      within(panneau).queryByRole("button", { name: /superutilisateur/i }),
    ).not.toBeInTheDocument();
  });

  it("bascule le statut par un geste distinct de l'enregistrement de la grille", async () => {
    updateRole.mockResolvedValue({ ...VALIDATOR, is_superuser: true });
    afficher();
    const panneau = await ouvrir("Validateur");

    await userEvent.click(within(panneau).getByRole("button", { name: /superutilisateur/i }));
    await confirmerDansLeDialog(/Poser le statut/);

    expect(updateRole).toHaveBeenCalledWith(VALIDATOR.id, { is_superuser: true });
  });

  it("confirme la bascule de superutilisateur sans la peindre en rouge", async () => {
    afficher();
    const panneau = await ouvrir("Validateur");

    const bascule = within(panneau).getByRole("button", { name: /superutilisateur/i });
    // Poser le statut n'est ni une fermeture d'accès ni une destruction : la
    // couleur reste neutre, seule la confirmation est due. (`aria-invalid:*`
    // porte "destructive" sur tout bouton, quel que soit son variant — c'est
    // `bg-destructive`, propre au variant, qui distingue vraiment.)
    expect(bascule.className).not.toContain("bg-destructive");

    await userEvent.click(bascule);
    await confirmerDansLeDialog("Renoncer");

    expect(updateRole).not.toHaveBeenCalled();
  });

  it("ne peint pas non plus en rouge le bouton d'action du dialog de la bascule", async () => {
    afficher();
    const panneau = await ouvrir("Validateur");

    await userEvent.click(within(panneau).getByRole("button", { name: /superutilisateur/i }));
    const dialog = await screen.findByRole("dialog");

    expect(
      within(dialog).getByRole("button", { name: /Poser le statut/ }).className,
    ).not.toContain("bg-destructive");

    await confirmerDansLeDialog("Renoncer");
  });
});

describe("RolePermissionsEditor — suppression", () => {
  it("n'offre pas la suppression d'un rôle livré, et dit pourquoi", async () => {
    afficher();
    const panneau = await ouvrir("Validateur");

    expect(within(panneau).getByRole("button", { name: "Supprimer" })).toBeDisabled();
    expect(panneau).toHaveTextContent("Rôle livré avec l'application.");
  });

  it("n'offre pas la suppression d'un rôle porté, et annonce le nombre", async () => {
    listRoles.mockResolvedValue([{ ...BENEVOLE, holders: 3 }]);
    afficher();
    const panneau = await ouvrir("Bénévole");

    expect(within(panneau).getByRole("button", { name: "Supprimer" })).toBeDisabled();
    expect(panneau).toHaveTextContent("Porté par 3 porteurs.");
  });

  it("supprime un rôle libre, après confirmation", async () => {
    deleteRole.mockResolvedValue(undefined);
    afficher();
    const panneau = await ouvrir("Bénévole");

    await userEvent.click(within(panneau).getByRole("button", { name: "Supprimer" }));
    await confirmerDansLeDialog("Supprimer définitivement");

    await vi.waitFor(() => expect(deleteRole).toHaveBeenCalledWith(BENEVOLE.id));
  });

  it("renonce si la confirmation est refusée", async () => {
    afficher();
    const panneau = await ouvrir("Bénévole");

    await userEvent.click(within(panneau).getByRole("button", { name: "Supprimer" }));
    await confirmerDansLeDialog("Renoncer");

    expect(deleteRole).not.toHaveBeenCalled();
  });

  it("ne supprime le rôle qu'après confirmation", async () => {
    deleteRole.mockResolvedValue(undefined);
    afficher();
    const panneau = await ouvrir("Bénévole");

    await userEvent.click(within(panneau).getByRole("button", { name: "Supprimer" }));
    expect(await screen.findByText(/Supprimer le rôle « .+ » \?/)).toBeTruthy();
    await confirmerDansLeDialog("Renoncer");

    expect(deleteRole).not.toHaveBeenCalled();
  });

  it("peint le bouton de suppression en rouge", async () => {
    afficher();
    const panneau = await ouvrir("Bénévole");

    expect(within(panneau).getByRole("button", { name: "Supprimer" }).className).toContain(
      "bg-destructive",
    );
  });

  it("peint aussi en rouge le bouton d'action du dialog de suppression", async () => {
    afficher();
    const panneau = await ouvrir("Bénévole");

    await userEvent.click(within(panneau).getByRole("button", { name: "Supprimer" }));
    const dialog = await screen.findByRole("dialog");

    expect(
      within(dialog).getByRole("button", { name: "Supprimer définitivement" }).className,
    ).toContain("bg-destructive");
  });
});

describe("RolePermissionsEditor — création", () => {
  it("ouvre la création depuis l'écran, avec l'inventaire déjà chargé", async () => {
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Créer un rôle" }));

    const modale = await screen.findByRole("dialog");
    expect(within(modale).getByLabelText(/identifiant/i)).toBeInTheDocument();
    expect(within(modale).getByRole("group", { name: "Rôles et accès" })).toBeInTheDocument();
  });

  /**
   * **La non-amplification ne s'arrête pas au bord de la modale.**
   *
   * `create_role` passe à `assert_may_grant` l'ensemble complet des codes
   * demandés, là où `update_role` ne lui passe que la différence symétrique :
   * une case cochable ici qui ne l'est pas dans un panneau, c'est un 403 promis
   * après que la personne a composé tout son rôle.
   */
  it("fige à la création les mêmes pouvoirs que dans un panneau", async () => {
    afficher({ ...SESSION, permissions: ["roles:write"], roles: [] });

    await userEvent.click(await screen.findByRole("button", { name: "Créer un rôle" }));
    const modale = await screen.findByRole("dialog");

    expect(within(modale).getByRole("checkbox", { name: /Composer les rôles/ })).toBeEnabled();
    expect(within(modale).getByRole("checkbox", { name: /Trancher la fiabilité/ })).toBeDisabled();
    expect(within(modale).getByRole("checkbox", { name: /Consulter les rôles/ })).toBeDisabled();
  });
});

describe("RolePermissionsEditor — ce que la session autorise", () => {
  /**
   * `roles:read` et `roles:write` sont deux pouvoirs distincts et attribuables
   * séparément : les lectures de l'écran exigent le premier, toutes ses
   * écritures le second. L'entrée de navigation filtre sur `roles:write`, mais
   * l'URL reste atteignable — sans cette garde, un porteur de `roles:read` seul
   * obtient un éditeur d'apparence complète dont chaque geste finit en 403.
   */
  it("rend l'écran en consultation à qui ne porte pas `roles:write`", async () => {
    afficher({ ...SESSION, permissions: ["roles:read"], roles: [] });

    expect(await screen.findByRole("button", { name: /Validateur/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Créer un rôle" })).not.toBeInTheDocument();
    expect(screen.getByText(/consultation/i)).toBeInTheDocument();

    const panneau = await ouvrir("Validateur");
    expect(within(panneau).queryByRole("button", { name: "Enregistrer" })).not.toBeInTheDocument();
    expect(within(panneau).queryByRole("button", { name: "Supprimer" })).not.toBeInTheDocument();
    expect(
      within(panneau).queryByRole("button", { name: /superutilisateur/i }),
    ).not.toBeInTheDocument();
    for (const case_ of within(panneau).getAllByRole("checkbox")) {
      expect(case_).toBeDisabled();
    }
  });

  /**
   * **Droits inconnus n'est pas droits nuls.**
   *
   * `useSession` ne réessaie pas : une panne sur `/auth/me` laisse `data` à
   * `undefined` pour de bon. Déduire de ce vide que l'utilisateur ne porte rien
   * fige les dix-huit cases en affirmant « vous ne portez pas ce pouvoir » — une
   * phrase fausse, y compris pour un superutilisateur.
   */
  it("ne prend pas une session en panne pour une absence de pouvoirs", async () => {
    afficher(new ApiError(500, "panne"));

    expect(await screen.findByText(/indisponibles/i)).toBeInTheDocument();
    expect(screen.queryByText(/ne portez pas ce pouvoir/i)).not.toBeInTheDocument();
  });
});

describe("RolePermissionsEditor — un brouillon face au serveur", () => {
  /**
   * **Le brouillon ne doit pas réécrire par-dessus autrui.**
   *
   * `permissions` remplace l'ensemble, et le panneau reste monté pendant que
   * `roles` se rafraîchit — une création depuis la même page suffit à
   * l'invalider. Sans garde, l'ensemble figé à l'ouverture repart au serveur et
   * efface ce qu'un autre administrateur vient d'ajouter, sans un mot. Le
   * serveur n'offre ni ETag ni `If-Match` : c'est ici que ça se voit ou nulle part.
   */
  it("ne réécrit pas par-dessus une recomposition arrivée pendant l'édition", async () => {
    const enrichi = { ...VALIDATOR, permissions: ["quality:override", "roles:write"] };
    listRoles.mockResolvedValueOnce([VALIDATOR]).mockResolvedValue([enrichi]);
    createRole.mockResolvedValue(BENEVOLE);
    afficher();
    const panneau = await ouvrir("Validateur");

    await userEvent.click(screen.getByRole("button", { name: "Créer un rôle" }));
    const modale = await screen.findByRole("dialog");
    await userEvent.type(within(modale).getByLabelText(/nom du rôle/i), "Bénévole");
    await userEvent.click(within(modale).getByRole("button", { name: "Créer le rôle" }));

    await vi.waitFor(() =>
      expect(within(panneau).getByText(/modifié ailleurs/i)).toBeInTheDocument(),
    );
    expect(within(panneau).getByRole("button", { name: "Enregistrer" })).toBeDisabled();
    expect(updateRole).not.toHaveBeenCalled();
  });

  /**
   * La bascule n'envoie que `is_superuser`, et la réponse rend l'état d'avant :
   * réinitialiser le brouillon sur elle jetterait la saisie en cours en
   * annonçant « Statut posé. ». Le rôle devenant superutilisateur, sa grille
   * passe inerte — les coches perdues ne seraient même pas refaisables.
   */
  it("ne bascule pas le statut par-dessus un brouillon non enregistré", async () => {
    afficher();
    const panneau = await ouvrir("Validateur");

    await userEvent.click(
      within(panneau).getByRole("checkbox", { name: /Consulter les rôles/ }),
    );

    expect(within(panneau).getByRole("button", { name: /superutilisateur/i })).toBeDisabled();
    expect(panneau).toHaveTextContent(/Enregistrez/i);
    expect(updateRole).not.toHaveBeenCalled();
  });

  /** `RoleUpdate.name` vaut `Field(min_length=1)` : le 422 revient en anglais. */
  it("n'envoie pas un nom vidé", async () => {
    afficher();
    const panneau = await ouvrir("Validateur");

    await userEvent.clear(within(panneau).getByLabelText(/nom du rôle/i));

    expect(within(panneau).getByRole("button", { name: "Enregistrer" })).toBeDisabled();
  });

  /** `RoleUpdate` n'a pas `str_strip_whitespace` : « Validateur   » s'enregistrerait tel quel. */
  it("ne compte pas un espace ajouté au nom comme une modification", async () => {
    afficher();
    const panneau = await ouvrir("Validateur");

    await userEvent.type(within(panneau).getByLabelText(/nom du rôle/i), "  ");

    expect(within(panneau).getByRole("button", { name: "Enregistrer" })).toBeDisabled();
  });

  it("laisse revenir sur une purge demandée", async () => {
    afficher();
    const panneau = await ouvrir("Bénévole");

    await userEvent.click(within(panneau).getByRole("button", { name: /^purger/i }));
    expect(within(panneau).getByText(/disparaîtr/i)).toBeInTheDocument();

    await userEvent.click(within(panneau).getByRole("button", { name: /annuler la purge/i }));
    expect(within(panneau).queryByText(/disparaîtr/i)).not.toBeInTheDocument();
  });

  /**
   * L'encadré lit l'état **connu du serveur**, pas la prop de la requête en
   * vol : sinon, entre la réponse de la purge et l'atterrissage du refetch,
   * l'écran continue d'énumérer des codes déjà supprimés et de proposer de les
   * purger — avec « Enregistrer » réactivé sur un écart qui n'existe plus.
   */
  it("retire l'encadré des codes périmés dès que la purge est acquittée", async () => {
    updateRole.mockResolvedValue({ ...BENEVOLE, stale_permissions: [] });
    afficher();
    const panneau = await ouvrir("Bénévole");

    await userEvent.click(within(panneau).getByRole("button", { name: /^purger/i }));
    await userEvent.click(within(panneau).getByRole("button", { name: "Enregistrer" }));

    await vi.waitFor(() =>
      expect(within(panneau).queryByRole("group", { name: /périmé/i })).not.toBeInTheDocument(),
    );
    expect(within(panneau).getByRole("button", { name: "Enregistrer" })).toBeDisabled();
  });
});
