import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Avatar } from "./Avatar";

describe("Avatar", () => {
  it("dérive les initiales du prénom et du nom", () => {
    render(<Avatar name="Marie Dupont" />);
    expect(screen.getByText("MD")).toBeInTheDocument();
  });

  it("pose les initiales en encre sur le dégradé orange", () => {
    // #299 : du blanc sur l'extrémité foncée du dégradé ne tenait que 3,68:1.
    render(<Avatar name="Marie Dupont" />);
    expect(screen.getByText("MD")).toHaveStyle({ color: "var(--tcn-ink)" });
  });
});
