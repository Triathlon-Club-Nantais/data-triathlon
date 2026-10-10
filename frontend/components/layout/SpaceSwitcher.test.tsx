import { render, screen } from "@testing-library/react";
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

const PUBLIC = { id: "public", label: "Résultats", href: "/dashboard" } as const;
const ADMIN = { id: "admin", label: "Back-office", href: "/admin", count: 214 } as const;

describe("SpaceSwitcher (#1296)", () => {
  it("ne rend rien avec un seul espace", () => {
    const { container } = render(<SpaceSwitcher current="public" spaces={[PUBLIC]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("annonce l'espace courant et liste les autres en liens", async () => {
    render(<SpaceSwitcher current="public" spaces={[PUBLIC, ADMIN]} />);
    await userEvent.click(screen.getByRole("button", { name: "Espace : Résultats, changer d'espace" }));
    expect(await screen.findByRole("menuitem", { name: /Back-office/ })).toHaveAttribute("href", "/admin");
    expect(screen.getByRole("menuitem", { name: /Résultats/ })).toHaveAttribute("aria-current", "true");
  });

  it("porte le compteur du back-office avec son nom accessible", async () => {
    render(<SpaceSwitcher current="public" spaces={[PUBLIC, ADMIN]} />);
    await userEvent.click(screen.getByRole("button", { name: /changer d'espace/ }));
    expect(await screen.findByText("214")).toBeInTheDocument();
    expect(screen.getByText("214 éléments à traiter")).toHaveClass("sr-only");
  });

  it("en mode compact, garde le nom accessible sans libellé visible", () => {
    render(<SpaceSwitcher current="public" spaces={[PUBLIC, ADMIN]} compact />);
    const bouton = screen.getByRole("button", { name: "Espace : Résultats, changer d'espace" });
    expect(bouton).not.toHaveTextContent("Résultats");
  });

  it("en mode compact, montre une infobulle et ouvre le menu", async () => {
    render(<SpaceSwitcher current="public" spaces={[PUBLIC, ADMIN]} compact />);
    const bouton = screen.getByRole("button", { name: /changer d'espace/ });
    await userEvent.hover(bouton);
    expect(await screen.findByRole("tooltip")).toBeInTheDocument();
    await userEvent.click(bouton);
    expect(await screen.findByRole("menuitem", { name: /Back-office/ })).toBeInTheDocument();
  });
});
