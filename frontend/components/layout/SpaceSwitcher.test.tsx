import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { SpaceSwitcher } from "./SpaceSwitcher";

vi.mock("next/link", () => ({
  default: ({ href, prefetch, children, ...rest }: { href: string; prefetch?: boolean; children?: ReactNode; [key: string]: unknown }) => (
    <a href={href} data-prefetch={String(prefetch)} {...rest}>
      {children}
    </a>
  ),
}));

const PUBLIC = { id: "public", label: "Consulter", href: "/" } as const;
const ENCADREMENT = { id: "encadrement", label: "Encadrement", href: "/encadrement" } as const;
const ADMIN = { id: "admin", label: "Back-office", href: "/admin", count: 214 } as const;

describe("SpaceSwitcher (#1336)", () => {
  it("ne rend rien avec un seul espace", () => {
    const { container } = render(<SpaceSwitcher current="public" spaces={[PUBLIC]} layout="row" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("en ligne, montre chaque espace en lien à icône et libellé, le courant marqué", () => {
    render(<SpaceSwitcher current="public" spaces={[PUBLIC, ENCADREMENT, ADMIN]} layout="row" />);
    const groupe = screen.getByRole("group", { name: "Espaces" });
    const liens = within(groupe).getAllByRole("link");
    expect(liens.map((l) => l.getAttribute("href"))).toEqual(["/", "/encadrement", "/admin"]);
    expect(within(groupe).getByRole("link", { name: "Consulter" })).toHaveAttribute("aria-current", "true");
    expect(within(groupe).getByRole("link", { name: "Encadrement" })).not.toHaveAttribute("aria-current");
    expect(within(groupe).getByRole("link", { name: "Consulter" })).toHaveTextContent("Consulter");
    expect(groupe.querySelector(".lucide-layout-grid")).not.toBeNull();
    expect(groupe.querySelector(".lucide-calendar-days")).not.toBeNull();
    expect(groupe.querySelector(".lucide-briefcase")).not.toBeNull();
  });

  it("porte le compteur en pastille décorative et dans le nom accessible", () => {
    render(<SpaceSwitcher current="public" spaces={[PUBLIC, ADMIN]} layout="row" />);
    const lien = screen.getByRole("link", { name: "Back-office, 214 éléments à traiter" });
    expect(within(lien).getByText("214")).toHaveAttribute("aria-hidden", "true");
  });

  it("en colonne, n'affiche que les icônes, nom accessible et infobulle compris", async () => {
    render(<SpaceSwitcher current="public" spaces={[PUBLIC, ADMIN]} layout="column" />);
    const lien = screen.getByRole("link", { name: "Consulter" });
    expect(lien).not.toHaveTextContent("Consulter");
    expect(lien).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("link", { name: "Back-office, 214 éléments à traiter" })).toHaveAttribute("href", "/admin");
    await userEvent.hover(lien);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Consulter");
  });

  it("laisse le survol aux tuiles inactives et tient 4,5:1 sur la tuile courante", () => {
    render(<SpaceSwitcher current="public" spaces={[PUBLIC, ENCADREMENT]} layout="row" />);
    const courant = screen.getByRole("link", { name: "Consulter" });
    const autre = screen.getByRole("link", { name: "Encadrement" });
    expect(courant).toHaveStyle({ color: "var(--tcn-orange-deeper)" });
    expect(autre).toHaveClass("tcn-space-tile");
    expect(autre.style.background).toBe("");
  });
});
