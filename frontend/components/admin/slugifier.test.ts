import { describe, it, expect } from "vitest";
import { slugifier } from "./CreateRoleDialog";

describe("slugifier", () => {
  it("folds accents and case into a slug", () => {
    expect(slugifier("Bénévole")).toBe("benevole");
    expect(slugifier("Responsable Équipe Jeunes")).toBe("responsable-equipe-jeunes");
  });

  it("drops spacing diacritics instead of turning them into a dash", () => {
    expect(slugifier("a^b`c")).toBe("abc");
  });

  it("turns apostrophes and punctuation into dashes, trimmed at both ends", () => {
    expect(slugifier("  L'équipe ! ")).toBe("l-equipe");
  });

  it("strips leading digits and dashes so the slug starts with a letter", () => {
    expect(slugifier("2e Coach")).toBe("e-coach");
  });
});
