import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "./dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./select";

// `--tcn-orange` on `--tcn-orange-10` composed on white is 3.25:1, under WCAG 1.4.3;
// `--tcn-orange-deeper` (`text-accent-ink`) reaches 5.09:1 (#1308).
function expectFocusStyles(element: HTMLElement) {
  const classes = element.className.split(" ");
  // Tailwind 4: `outline-hidden`/`outline-none` would cancel `outline-2` (#1305).
  expect(classes).not.toContain("outline-hidden");
  expect(classes).not.toContain("outline-none");
  expect(classes).toContain("focus-visible:outline-2");
  expect(classes).toContain("focus-visible:-outline-offset-2");
  expect(classes).toContain("focus-visible:outline-[var(--tcn-orange)]");
  expect(classes).toContain("focus:bg-accent");
  expect(element.className).not.toContain("text-accent-foreground");
  expect(classes).toContain("focus:text-accent-ink");
}

describe("dropdown menu items focus (#1305, #1308)", () => {
  it("draw an opaque inset outline and keep an AA text color", () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Modifier</DropdownMenuItem>
          <DropdownMenuCheckboxItem checked>Cocher</DropdownMenuCheckboxItem>
          <DropdownMenuRadioGroup value="a">
            <DropdownMenuRadioItem value="a">Choisir</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>Plus</DropdownMenuSubTrigger>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    expectFocusStyles(screen.getByRole("menuitem", { name: "Modifier" }));
    expectFocusStyles(screen.getByRole("menuitemcheckbox", { name: "Cocher" }));
    expectFocusStyles(screen.getByRole("menuitemradio", { name: "Choisir" }));
    const subTrigger = screen.getByRole("menuitem", { name: "Plus" });
    expectFocusStyles(subTrigger);
    expect(subTrigger.className.split(" ")).toContain("data-popup-open:text-accent-ink");
  });

  it("keep the destructive variant on its danger color", () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem variant="destructive">Supprimer</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    const classes = screen.getByRole("menuitem", { name: "Supprimer" }).className.split(" ");
    expect(classes).toContain("data-[variant=destructive]:focus:text-destructive");
    expect(classes).toContain("not-data-[variant=destructive]:focus:**:text-accent-ink");
  });
});

describe("select items focus (#1308)", () => {
  it("draw an opaque inset outline and keep an AA text color", () => {
    render(
      <Select defaultOpen defaultValue="a">
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="a">Toutes</SelectItem>
        </SelectContent>
      </Select>,
    );

    expectFocusStyles(screen.getByRole("option", { name: "Toutes" }));
  });
});
