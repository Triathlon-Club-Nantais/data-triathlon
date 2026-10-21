import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useEstCompact } from "./useEstCompact";

afterEach(() => vi.unstubAllGlobals());

describe("useEstCompact (#1774)", () => {
  it("asks for the `lg` breakpoint: below it the 288 px sidebar leaves no room for two columns", () => {
    const matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener() {}, removeEventListener() {} });
    vi.stubGlobal("matchMedia", matchMedia);

    const { result } = renderHook(() => useEstCompact());

    expect(result.current).toBe(true);
    expect(matchMedia).toHaveBeenCalledWith("(max-width: 1023px)");
  });
});
