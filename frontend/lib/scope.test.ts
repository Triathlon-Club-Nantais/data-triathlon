import { describe, expect, it } from "vitest";
import { SCOPE_CLUB, federalOnlyFromParam, genderFromSexeParam, scopeFromParam } from "./scope";

describe("scopeFromParam", () => {
  it("rend la portée club quand le paramètre la demande", () => {
    expect(scopeFromParam("club")).toBe(SCOPE_CLUB);
  });

  it("rend undefined sinon, pour que le filtre soit simplement absent", () => {
    expect(scopeFromParam(undefined)).toBeUndefined();
    expect(scopeFromParam(null)).toBeUndefined();
    expect(scopeFromParam("tous")).toBeUndefined();
  });
});

describe("federalOnlyFromParam", () => {
  it("filtre les autres disciplines par défaut", () => {
    expect(federalOnlyFromParam(undefined)).toBe(true);
    expect(federalOnlyFromParam(null)).toBe(true);
  });

  it("rend undefined quand l'utilisateur demande tout, pour ne rien envoyer à l'API", () => {
    expect(federalOnlyFromParam("all")).toBeUndefined();
  });
});

describe("genderFromSexeParam", () => {
  it("maps sexe URL values to API gender", () => {
    expect(genderFromSexeParam("H")).toBe("M");
    expect(genderFromSexeParam("F")).toBe("F");
    expect(genderFromSexeParam("x")).toBeUndefined();
    expect(genderFromSexeParam(undefined)).toBeUndefined();
  });
});
