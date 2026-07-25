import { describe, expect, it } from "vitest";
import { SCOPE_CLUB, isClubScope, scopeFromParam } from "./scope";

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

describe("isClubScope", () => {
  it("reconnaît la portée club", () => {
    expect(isClubScope("club")).toBe(true);
    expect(isClubScope(undefined)).toBe(false);
  });
});
