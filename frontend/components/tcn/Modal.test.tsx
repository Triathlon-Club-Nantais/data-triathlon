import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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

    expect(screen.getByRole("button", { name: "Fermer" })).toHaveFocus();
  });

  it("piège le focus : Shift+Tab depuis le premier élément va au dernier", async () => {
    const user = userEvent.setup();
    render(<Scenario onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Fermer" }));
    await user.tab({ shift: true });

    expect(screen.getByRole("button", { name: "Dernier" })).toHaveFocus();
  });

  it("restaure le focus sur le déclencheur à la fermeture", async () => {
    const user = userEvent.setup();
    const ouvrir = document.createElement("button");
    ouvrir.textContent = "Ouvrir";
    document.body.appendChild(ouvrir);
    ouvrir.focus();

    const { unmount } = render(<Modal title="Titre" onClose={vi.fn()} />);
    expect(ouvrir).not.toHaveFocus();

    unmount();

    expect(ouvrir).toHaveFocus();
    document.body.removeChild(ouvrir);
    void user;
  });
});
