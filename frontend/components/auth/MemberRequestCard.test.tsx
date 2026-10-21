import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { MemberRequest, SessionUser } from "@/lib/types";

const { requestMembership, cancelMembershipRequest, getSession } = vi.hoisted(() => ({
  requestMembership: vi.fn(),
  cancelMembershipRequest: vi.fn(),
  getSession: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, requestMembership, cancelMembershipRequest, getSession } };
});

import { MemberRequestCard } from "./MemberRequestCard";

const REQUEST: MemberRequest = {
  id: 1,
  status: "pending",
  first_name: "Camille",
  last_name: "Martin",
  birth_date: null,
  phone: "0612345678",
  created_at: "2026-10-21T10:00:00Z",
  decided_at: null,
};

function afficher(memberRequest: MemberRequest | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const session = { id: 1, member_request: memberRequest } as unknown as SessionUser;
  getSession.mockResolvedValue(session);
  return render(
    <QueryClientProvider client={client}>
      <MemberRequestCard session={session} />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.useRealTimers());

describe("MemberRequestCard", () => {
  it("envoie prénom, nom et téléphone", async () => {
    requestMembership.mockResolvedValue(REQUEST);
    afficher();

    await userEvent.type(screen.getByLabelText("Prénom"), "Camille");
    await userEvent.type(screen.getByLabelText("Nom"), "Martin");
    await userEvent.type(screen.getByLabelText("Téléphone"), "0612345678");
    await userEvent.click(screen.getByRole("button", { name: "Demander à rejoindre le TCN" }));

    expect(requestMembership).toHaveBeenCalledWith({
      first_name: "Camille",
      last_name: "Martin",
      birth_date: null,
      phone: "0612345678",
    });
  });

  it("refuse l'envoi sans date de naissance ni téléphone", async () => {
    afficher();

    await userEvent.type(screen.getByLabelText("Prénom"), "Camille");
    await userEvent.type(screen.getByLabelText("Nom"), "Martin");
    await userEvent.click(screen.getByRole("button", { name: /Demander à rejoindre/ }));

    expect(screen.getByRole("alert")).toHaveTextContent("Indiquez votre date de naissance ou votre téléphone.");
    expect(requestMembership).not.toHaveBeenCalled();
  });

  it("montre l'attente et permet d'annuler", async () => {
    cancelMembershipRequest.mockResolvedValue(null);
    afficher(REQUEST);

    expect(screen.getByText(/en attente : un administrateur du club la valide/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Prénom")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Annuler la demande" }));

    expect(cancelMembershipRequest).toHaveBeenCalled();
  });

  it("affiche le refus du serveur", async () => {
    requestMembership.mockRejectedValue(
      new ApiError(409, "Votre demande a été refusée. Vous pourrez en envoyer une nouvelle à partir du 01/12/2026."),
    );
    afficher({ ...REQUEST, status: "rejected", decided_at: "2026-01-02T10:00:00Z" });

    expect(screen.getByText("Votre précédente demande a été refusée.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Prénom"), "Camille");
    await userEvent.type(screen.getByLabelText("Nom"), "Martin");
    await userEvent.type(screen.getByLabelText("Téléphone"), "0612345678");
    await userEvent.click(screen.getByRole("button", { name: /Demander à rejoindre/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("à partir du 01/12/2026");
  });

  it("refuse un prénom ou un nom vide", async () => {
    afficher();

    await userEvent.type(screen.getByLabelText("Prénom"), "   ");
    await userEvent.type(screen.getByLabelText("Nom"), "Martin");
    await userEvent.type(screen.getByLabelText("Téléphone"), "0612345678");
    await userEvent.click(screen.getByRole("button", { name: /Demander à rejoindre/ }));

    expect(screen.getByRole("alert")).toHaveTextContent("Indiquez votre prénom et votre nom.");
    expect(requestMembership).not.toHaveBeenCalled();
  });

  it("signale les champs en erreur, les relie à l'alerte et y place le focus", async () => {
    afficher();

    await userEvent.type(screen.getByLabelText("Prénom"), "   ");
    await userEvent.type(screen.getByLabelText("Nom"), "Martin");
    await userEvent.click(screen.getByRole("button", { name: /Demander à rejoindre/ }));

    const alerte = screen.getByRole("alert");
    const prenom = screen.getByLabelText("Prénom");
    expect(prenom).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Nom")).not.toHaveAttribute("aria-invalid");
    expect(prenom).toHaveAttribute("aria-describedby", alerte.id);
    expect(prenom).toHaveFocus();
    expect(screen.getByLabelText("Téléphone")).not.toHaveAttribute("aria-invalid");

    await userEvent.clear(screen.getByLabelText("Prénom"));
    await userEvent.type(screen.getByLabelText("Prénom"), "Camille");
    await userEvent.click(screen.getByRole("button", { name: /Demander à rejoindre/ }));
    expect(screen.getByLabelText("Prénom")).not.toHaveAttribute("aria-invalid");
  });

  it("signale date de naissance et téléphone quand les deux manquent", async () => {
    afficher();

    await userEvent.type(screen.getByLabelText("Prénom"), "Camille");
    await userEvent.type(screen.getByLabelText("Nom"), "Martin");
    await userEvent.click(screen.getByRole("button", { name: /Demander à rejoindre/ }));

    expect(screen.getByLabelText("Date de naissance")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Téléphone")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Date de naissance")).toHaveFocus();
  });

  it("affiche « Envoi… » pendant l'envoi", async () => {
    requestMembership.mockReturnValue(new Promise(() => {}));
    afficher();

    await userEvent.type(screen.getByLabelText("Prénom"), "Camille");
    await userEvent.type(screen.getByLabelText("Nom"), "Martin");
    await userEvent.type(screen.getByLabelText("Téléphone"), "0612345678");
    await userEvent.click(screen.getByRole("button", { name: /Demander à rejoindre/ }));

    expect(await screen.findByRole("button", { name: "Envoi…" })).toBeInTheDocument();
  });

  it("masque le formulaire jusqu'à la fin du délai après un refus", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-11-20T10:00:00Z") });
    afficher({ ...REQUEST, status: "rejected", decided_at: "2026-10-22T23:30:00Z" });

    expect(
      screen.getByText("Votre précédente demande a été refusée. Vous pourrez en envoyer une nouvelle à partir du 21/11/2026."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Prénom")).toBeNull();
  });

  it("rouvre le formulaire le jour de la date annoncée", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-11-21T00:30:00Z") });
    afficher({ ...REQUEST, status: "rejected", decided_at: "2026-10-22T23:30:00Z" });

    expect(screen.getByLabelText("Prénom")).toBeInTheDocument();
  });

  it("déplace le focus sur le titre quand la carte change d'état", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const avec = (memberRequest: MemberRequest | null) => (
      <QueryClientProvider client={client}>
        <MemberRequestCard session={{ id: 1, member_request: memberRequest } as unknown as SessionUser} />
      </QueryClientProvider>
    );
    const { rerender } = render(avec(null));
    expect(screen.getByRole("heading", { name: "Adhésion au club" })).not.toHaveFocus();

    rerender(avec(REQUEST));
    expect(screen.getByRole("heading", { name: "Adhésion au club" })).toHaveFocus();

    rerender(avec(null));
    expect(screen.getByRole("heading", { name: "Adhésion au club" })).toHaveFocus();
  });
});
