import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Tabs, TabsList, TabsTrigger } from "./tabs";

describe("TabsTrigger", () => {
  it("writes inactive labels in `text-muted-foreground`, not `text-foreground/60` (#950)", () => {
    // `foreground/60` composed on `bg-muted` gives 4.28:1, under the 4.5:1 of WCAG 1.4.3.
    render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">Performance</TabsTrigger>
          <TabsTrigger value="b">Par mois</TabsTrigger>
        </TabsList>
      </Tabs>,
    );

    const classes = screen.getByRole("tab", { name: "Par mois" }).className.split(" ");
    expect(classes).toContain("text-muted-foreground");
    expect(classes).not.toContain("text-foreground/60");
    expect(classes).toContain("hover:text-foreground");
    expect(classes).toContain("data-active:text-foreground");
  });
});
