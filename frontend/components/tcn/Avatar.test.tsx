import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Avatar } from "./Avatar";

describe("Avatar", () => {
  it("dérive les initiales du prénom et du nom", () => {
    render(<Avatar name="Marie Dupont" />);
    expect(screen.getByText("MD")).toBeInTheDocument();
  });

  it("pose les initiales en blanc sur le dégradé orange", () => {
    // #299 : le blanc reste, c'est le dégradé qui a été assombri pour le porter
    // — il descendait à #E9530E, où le blanc ne tenait que 3,68:1. Le seuil du
    // dégradé lui-même est vérifié dans `app/globals.test.ts`.
    render(<Avatar name="Marie Dupont" />);
    expect(screen.getByText("MD")).toHaveStyle({ color: "#fff" });
  });
});
