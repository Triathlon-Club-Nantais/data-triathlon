import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { Modal } from "./Modal";

function Scenario({ onClose }: { onClose: () => void }) {
  return (
    <div>
      <button type="button">Ouvrir</button>
      <Modal title="Titre" onClose={onClose}>
        <button type="button">Premier</button>
        <button type="button">Dernier</button>
      </Modal>
    </div>
  );
}

describe("Modal — piège et restauration du focus (NAV-8, #484)", () => {
  it("piège le focus : Tab depuis le dernier élément revient au premier", async () => {
    const user = userEvent.setup();
    render(<Scenario onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Dernier" }));
    await user.tab();

    await waitFor(() => expect(screen.getByRole("button", { name: "Fermer" })).toHaveFocus());
  });

  it("piège le focus : Shift+Tab depuis le premier élément va au dernier", async () => {
    const user = userEvent.setup();
    render(<Scenario onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Fermer" }));
    await user.tab({ shift: true });

    await waitFor(() => expect(screen.getByRole("button", { name: "Dernier" })).toHaveFocus());
  });

  it("restaure le focus sur le déclencheur à la fermeture", async () => {
    const ouvrir = document.createElement("button");
    ouvrir.textContent = "Déclencheur";
    document.body.appendChild(ouvrir);
    ouvrir.focus();
    try {
      const { unmount } = render(<Modal title="Titre" onClose={vi.fn()} />);
      await waitFor(() => expect(ouvrir).not.toHaveFocus());

      unmount();

      await waitFor(() => expect(ouvrir).toHaveFocus());
    } finally {
      ouvrir.remove();
    }
  });
});

describe("Modal — initial focus (#955)", () => {
  it("focuses the first focusable element when no child claims focus", async () => {
    render(<Scenario onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Fermer" })).toHaveFocus());
  });

  it("leaves focus on a child that took it through autoFocus", async () => {
    render(
      <Modal title="Titre">
        <input autoFocus placeholder="q" />
      </Modal>,
    );

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.getByPlaceholderText("q")).toHaveFocus();
  });

  it("still restores focus to the trigger when a child used autoFocus", async () => {
    const ouvrir = document.createElement("button");
    ouvrir.textContent = "Déclencheur";
    document.body.appendChild(ouvrir);
    ouvrir.focus();
    try {
      const { unmount } = render(
        <Modal title="Titre">
          <input autoFocus placeholder="q" />
        </Modal>,
      );
      await waitFor(() => expect(screen.getByPlaceholderText("q")).toHaveFocus());
      unmount();

      await waitFor(() => expect(ouvrir).toHaveFocus());
    } finally {
      ouvrir.remove();
    }
  });
});

function Page({ withAutoFocus = false }: { withAutoFocus?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Ouvrir
      </button>
      <a href="#derriere">Derrière</a>
      <Modal open={open} title="Titre" onClose={() => setOpen(false)}>
        {withAutoFocus ? <input autoFocus placeholder="q" /> : null}
        <button type="button">Premier</button>
        <button type="button">Dernier</button>
      </Modal>
    </div>
  );
}

describe("Modal: robust focus trap and restore (#988)", () => {
  it("keeps Tab inside the dialog after a click on a non focusable area", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.click(screen.getByRole("button", { name: "Ouvrir" }));
    const dialog = screen.getByRole("dialog");

    await user.click(screen.getByText("Titre"));
    await user.tab();
    await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));

    await user.click(screen.getByText("Titre"));
    await user.tab({ shift: true });
    await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));
  });

  it("returns focus to the opening button on Escape when a child used autoFocus", async () => {
    const user = userEvent.setup();
    render(<Page withAutoFocus />);
    const ouvrir = screen.getByRole("button", { name: "Ouvrir" });

    await user.click(ouvrir);
    await waitFor(() => expect(screen.getByPlaceholderText("q")).toHaveFocus());
    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(ouvrir).toHaveFocus());
  });

  it("still closes on a click outside the panel", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Modal title="Titre" onClose={onClose} />);
    const dialog = screen.getByRole("dialog");

    await user.click(dialog.parentElement as HTMLElement);

    expect(onClose).toHaveBeenCalled();
  });
});
