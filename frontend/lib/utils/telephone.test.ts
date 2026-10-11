import { describe, expect, it } from "vitest";
import { trouverTelephone } from "./telephone";

describe("trouverTelephone", () => {
  it.each([
    ["Mère 06 00 00 00 00", "06 00 00 00 00", "tel:0600000000"],
    ["Parent X 0612345678 (soir)", "0612345678", "tel:0612345678"],
    ["06.12.34.56.78", "06.12.34.56.78", "tel:0612345678"],
    ["Père : 06-12-34-56-78", "06-12-34-56-78", "tel:0612345678"],
    ["+33 6 12 34 56 78", "+33 6 12 34 56 78", "tel:+33612345678"],
    ["02 40 00 00 00 (fixe)", "02 40 00 00 00", "tel:0240000000"],
    ["Mère 0033 6 12 34 56 78", "0033 6 12 34 56 78", "tel:+33612345678"],
    ["+33 (0)6 12 34 56 78", "+33 (0)6 12 34 56 78", "tel:+33612345678"],
    ["Père 0612 345 678 le soir", "0612 345 678", "tel:0612345678"],
  ])("repère le numéro dans « %s »", (texte, numero, href) => {
    const trouve = trouverTelephone(texte);

    expect(trouve && texte.slice(trouve.debut, trouve.fin)).toBe(numero);
    expect(trouve?.href).toBe(href);
  });

  it.each(["Voir avec le club", "", "Né en 2015, licence 123456", "06 00 00"])(
    "ne repère rien dans « %s »",
    (texte) => {
      expect(trouverTelephone(texte)).toBeNull();
    },
  );
});
