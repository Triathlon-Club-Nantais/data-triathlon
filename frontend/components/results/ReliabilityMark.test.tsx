import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SplitCoverageNote } from "./ReliabilityMark";

describe("SplitCoverageNote", () => {
  it("lie le « % » à son nombre par une espace fine insécable (#1600)", () => {
    const { container } = render(<SplitCoverageNote median={0.04} rows={20} />);
    expect(container.textContent).toContain("environ 4\u202f% du temps total");
  });
});
