import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

import { GlobalSearch } from "./GlobalSearch";

describe("GlobalSearch", () => {
  it("ouvre le dialog de recherche sans lever d'erreur au clic", async () => {
    const user = userEvent.setup();
    render(<GlobalSearch />);

    await user.click(screen.getByRole("button", { name: /Rechercher un athlète/i }));

    // Le champ de recherche (primitive cmdk) doit se monter dans le dialog.
    expect(
      await screen.findByPlaceholderText("Nom d'un athlète…"),
    ).toBeInTheDocument();
  });
});
