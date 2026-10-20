import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

const push = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(search),
  usePathname: () => "/chemin",
}));

import { SexeToggle } from "./SexeToggle";

beforeEach(() => {
  push.mockClear();
  search = "";
});

describe("SexeToggle", () => {
  it("renders Tous, Hommes, Femmes inside a group labelled Sexe", () => {
    render(<SexeToggle />);
    const group = screen.getByRole("group", { name: "Sexe" });
    expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Tous",
      "Hommes",
      "Femmes",
    ]);
  });

  it("marks Femmes as selected when sexe=F", () => {
    search = "sexe=F";
    render(<SexeToggle />);
    expect(screen.getByRole("button", { name: "Femmes" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Tous" })).toHaveAttribute("aria-pressed", "false");
  });

  it("treats an invalid sexe value as Tous", () => {
    search = "sexe=x";
    render(<SexeToggle />);
    expect(screen.getByRole("button", { name: "Tous" })).toHaveAttribute("aria-pressed", "true");
  });

  it("pushes sexe=F and drops page when Femmes is clicked", () => {
    search = "page=3&scope=club";
    render(<SexeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Femmes" }));
    expect(push).toHaveBeenCalledWith("/chemin?scope=club&sexe=F");
  });

  it("removes sexe when Tous is clicked", () => {
    search = "sexe=H";
    render(<SexeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Tous" }));
    expect(push).toHaveBeenCalledWith("/chemin");
  });
});
