import { describe, it, expect } from "vitest";
import Icon, { contentType } from "./icon";

describe("Icon", () => {
  it("génère un PNG non vide", async () => {
    const response = Icon();

    expect(response.headers.get("content-type")).toBe(contentType);

    const buffer = await response.arrayBuffer();
    expect(buffer.byteLength).toBeGreaterThan(100);
  });
});
