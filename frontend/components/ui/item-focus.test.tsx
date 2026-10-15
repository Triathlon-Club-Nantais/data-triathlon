import { describe, it, expect } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

// Ink text on `--tcn-orange-08` is 15.1:1; the former `--tcn-orange` text was 3.33:1 (#1308).
function expectFocusStyles(element: HTMLElement) {
  const classes = element.className.split(" ");
  // Tailwind 4: `outline-hidden`/`outline-none` would cancel `outline-2` (#1305).
  expect(classes).not.toContain("outline-hidden");
  expect(classes).not.toContain("outline-none");
  expect(classes).toContain("focus-visible:outline-2");
  expect(classes).toContain("focus-visible:-outline-offset-2");
  expect(classes).toContain("focus-visible:outline-[var(--tcn-orange)]");
  expect(classes).toContain("data-highlighted:bg-[var(--tcn-orange-08)]");
  expect(element.className).not.toContain("accent");
}

describe("dropdown menu items focus (#1305, #1308)", () => {
  it("draw an opaque inset outline and keep the ink text", () => {
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
    expectFocusStyles(screen.getByRole("menuitem", { name: "Plus" }));
  });

  it("moves real DOM focus onto the item from the keyboard, the premise of focus-visible", async () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Modifier</DropdownMenuItem>
          <DropdownMenuItem>Supprimer</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    const item = screen.getByRole("menuitem", { name: "Modifier" });
    expect(document.activeElement).not.toBe(item);

    fireEvent.keyDown(screen.getByRole("menu"), { key: "ArrowDown" });

    await waitFor(() => expect(document.activeElement).toBe(item));
  });
});

describe("select trigger focus (#1332)", () => {
  it("draws an opaque outset outline, not the 1.93:1 ring alone", () => {
    render(
      <Select defaultValue="a">
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="a">Toutes</SelectItem>
        </SelectContent>
      </Select>,
    );

    const classes = screen.getByRole("combobox").className.split(" ");
    expect(classes).not.toContain("outline-none");
    expect(classes).toContain("focus-visible:outline-2");
    expect(classes).toContain("focus-visible:outline-offset-2");
    expect(classes).toContain("focus-visible:outline-[var(--tcn-orange)]");
  });
});

describe("select items focus (#1308)", () => {
  it("draw an opaque inset outline and keep the ink text", () => {
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
