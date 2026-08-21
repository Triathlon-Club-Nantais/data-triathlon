import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import type { ReactElement } from "react";

import GlobalError from "./global-error";

/**
 * `global-error` doit rendre `<html>` et `<body>` lui-même. Les imbriquer dans
 * la `<div>` de RTL déclencherait un avertissement `validateDOMNesting`, donc on
 * inspecte l'élément racine sans le monter, puis on monte le contenu du `<body>`.
 */
function documenter() {
  const arbre = GlobalError({
    error: Object.assign(new Error("boum"), { digest: "4f3c9a12" }),
    retry: vi.fn(),
  }) as ReactElement<{ children: ReactElement<{ children: React.ReactNode }> }>;
  return { arbre, corps: arbre.props.children.props.children };
}

describe("app/global-error", () => {
  it("rend son propre document, déclaré en français (WCAG 2.2 3.1.1, #464)", () => {
    const { arbre } = documenter();

    expect(arbre.type).toBe("html");
    expect(arbre.props).toMatchObject({ lang: "fr" });
  });

  it("porte l'écran de panne, que le layout racine remplacé ne fournit plus", () => {
    render(<>{documenter().corps}</>);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /n'a pas pu s'afficher/i,
    );
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });

  it("porte son propre bouton de signalement, le layout racine ayant disparu", () => {
    render(<>{documenter().corps}</>);

    expect(screen.getByRole("button", { name: /signaler un bug/i })).toBeInTheDocument();
  });
});
