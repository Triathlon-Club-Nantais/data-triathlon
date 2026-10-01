import { describe, expect, it } from "vitest";
import { cheminDeRetour } from "@/lib/site-access-return";

describe("cheminDeRetour", () => {
  it("garde un chemin interne", () => {
    expect(cheminDeRetour("/admin/utilisateurs")).toBe("/admin/utilisateurs");
    expect(cheminDeRetour("/courses/42?onglet=resultats")).toBe("/courses/42?onglet=resultats");
  });

  it.each([undefined, "", "https://evil.example", "//evil.example", "/\\evil.example", "admin"])(
    "refuse %s : jamais de redirection hors du site",
    (brut) => {
      expect(cheminDeRetour(brut)).toBeNull();
    },
  );
});
