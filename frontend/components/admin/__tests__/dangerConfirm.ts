import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/** Vise le bouton du dialog plutôt que celui de la ligne ou du panneau : les
 *  deux partagent parfois le même libellé, mais seul le premier vit dans
 *  `role="dialog"`. */
export async function confirmerDansLeDialog(nom: RegExp | string) {
  const dialog = await screen.findByRole("dialog");
  await userEvent.click(within(dialog).getByRole("button", { name: nom }));
}
