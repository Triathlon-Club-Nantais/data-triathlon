import { describe, expect, it } from "vitest";
import { cheminDeRetour } from "@/lib/site-access-return";

describe("cheminDeRetour", () => {
  it("garde un chemin interne", () => {
    expect(cheminDeRetour("/admin/utilisateurs")).toBe("/admin/utilisateurs");
    expect(cheminDeRetour("/courses/42?onglet=resultats")).toBe("/courses/42?onglet=resultats");
  });

  it.each([
    undefined,
    "",
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "admin",
    // Le parseur d'URL retire tabulations et sauts de ligne : « /\t/x » devient « //x ».
    "/\t/evil.example",
    "/\n/evil.example",
    "/\r/evil.example",
    "/\t\\evil.example",
    // La normalisation des segments « . » et « .. » peut rendre un chemin qui commence par « // ».
    "/.//evil.example",
    "/a/..//evil.example",
    "/%2e//evil.example",
    "/.%2e//evil.example",
    "/./\\evil.example",
    "/\t.//evil.example",
  ])(
    "refuse %s : jamais de redirection hors du site",
    (brut) => {
      expect(cheminDeRetour(brut)).toBeNull();
    },
  );
});
