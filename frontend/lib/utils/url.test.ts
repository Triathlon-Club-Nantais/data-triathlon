import { describe, it, expect } from "vitest";
import { isHttpUrl } from "./url";

describe("isHttpUrl", () => {
  it("accepte http et https", () => {
    expect(isHttpUrl("http://klikego.com/x")).toBe(true);
    expect(isHttpUrl("https://www.klikego.com/resultats/x")).toBe(true);
  });

  it("rejette les schémas non web", () => {
    expect(isHttpUrl("javascript:alert(1)")).toBe(false);
    expect(isHttpUrl("data:text/html,<script>")).toBe(false);
    expect(isHttpUrl("ftp://exemple.com/f")).toBe(false);
  });

  it("rejette le vide et l'invalide", () => {
    expect(isHttpUrl("")).toBe(false);
    expect(isHttpUrl(null)).toBe(false);
    expect(isHttpUrl(undefined)).toBe(false);
    expect(isHttpUrl("pas une url")).toBe(false);
  });
});
