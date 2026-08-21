import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Children, isValidElement, type ReactElement, type ReactNode } from "react";

const { captureEvent } = vi.hoisted(() => ({ captureEvent: vi.fn() }));
vi.mock("@/lib/posthog", () => ({ captureEvent }));

import GlobalError from "./global-error";

/**
 * `global-error` doit rendre `<html>` et `<body>` lui-même. Les imbriquer dans la
 * `<div>` de RTL déclencherait un avertissement `validateDOMNesting`, donc on
 * inspecte l'élément racine sans le monter, puis on monte le contenu du `<body>`.
 *
 * Le `<body>` se **cherche** parmi les enfants au lieu de se supposer unique :
 * ajouter un `<head>` un jour est un changement correct, et il ne doit pas faire
 * tomber ces trois tests sur un `TypeError` opaque.
 */
function documenter(retry = vi.fn()) {
  const arbre = GlobalError({
    error: Object.assign(new Error("boum"), { digest: "4f3c9a12" }),
    retry,
  }) as ReactElement<{ children: ReactNode; style?: Record<string, string>; lang?: string }>;
  const corps = Children.toArray(arbre.props.children).find(
    (enfant): enfant is ReactElement<{ children: ReactNode }> =>
      isValidElement(enfant) && enfant.type === "body",
  );
  if (!corps) throw new Error("global-error ne rend pas de <body>");
  return { arbre, corps: corps.props.children, retry };
}

describe("app/global-error", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rend son propre document, déclaré en français (WCAG 2.2 3.1.1, #464)", () => {
    const { arbre } = documenter();

    expect(arbre.type).toBe("html");
    expect(arbre.props).toMatchObject({ lang: "fr" });
  });

  it("définit les variables next/font qu'il ne charge pas (#464, D2)", () => {
    const { arbre } = documenter();

    // `--tcn-font-body` vaut `var(--font-barlow), system-ui, sans-serif`. Sans
    // `--font-barlow`, toute la déclaration devient invalide à la substitution
    // (CSS Custom Properties, « Invalid At Computed-Value Time ») : la queue
    // `system-ui` n'est jamais atteinte et le document tombe en serif.
    expect(arbre.props.style).toMatchObject({
      "--font-anton": expect.any(String),
      "--font-barlow": expect.any(String),
      "--font-barlow-cond": expect.any(String),
    });
  });

  it("porte l'écran de panne, que le layout racine remplacé ne fournit plus", () => {
    render(<>{documenter().corps}</>);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /n'a pas pu s'afficher/i,
    );
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });

  it("câble « Réessayer » sur retry(), et pas sur rien", async () => {
    const { corps, retry } = documenter();
    const user = userEvent.setup();
    render(<>{corps}</>);

    await user.click(screen.getByRole("button", { name: "Réessayer" }));

    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("transmet le code d'incident, pour qu'un signalement reste exploitable", () => {
    render(<>{documenter().corps}</>);

    expect(screen.getByText(/4f3c9a12/)).toBeInTheDocument();
  });

  it("titre le document en français, `metadata` étant ignoré dans un composant client", () => {
    render(<>{documenter().corps}</>);

    expect(document.title).toBe("Erreur — TCN");
  });

  it("porte son propre bouton de signalement, le layout racine ayant disparu", () => {
    render(<>{documenter().corps}</>);

    expect(screen.getByRole("button", { name: /signaler un bug/i })).toBeInTheDocument();
  });

  it("compte l'affichage comme la frontière de page, la panne étant pire ici", () => {
    render(<>{documenter().corps}</>);

    expect(captureEvent).toHaveBeenCalledWith("error_screen_shown", { digest: "4f3c9a12" });
  });
});
