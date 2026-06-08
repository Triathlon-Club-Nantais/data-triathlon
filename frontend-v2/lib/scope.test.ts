import { describe, it, expect } from "vitest";
import { clubFromScope, isClubScope, SCOPE_CLUB } from "./scope";
import { TCN_CLUB_FILTER } from "./club-constants";

describe("scope", () => {
  it("clubFromScope renvoie le filtre club quand scope=club", () => {
    expect(clubFromScope(SCOPE_CLUB)).toBe(TCN_CLUB_FILTER);
  });
  it("clubFromScope renvoie undefined sinon", () => {
    expect(clubFromScope(undefined)).toBeUndefined();
    expect(clubFromScope(null)).toBeUndefined();
    expect(clubFromScope("autre")).toBeUndefined();
  });
  it("isClubScope détecte la portée club", () => {
    expect(isClubScope(SCOPE_CLUB)).toBe(true);
    expect(isClubScope(undefined)).toBe(false);
  });
});
