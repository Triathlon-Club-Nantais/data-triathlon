import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

// `useSession` (#427) n'appelle `/auth/me` que si ce cookie est présent —
// posé par défaut ici pour que les tests existants, qui simulent une session
// via `apiClient.getSession`, gardent leur comportement sans le poser
// individuellement. Un test du visiteur anonyme l'efface explicitement.
if (typeof document !== "undefined") {
  beforeEach(() => {
    document.cookie = "tcn_logged_in=1; path=/";
  });
}

// jsdom ne fournit pas ResizeObserver, requis par les primitives `@base-ui/react`.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// jsdom n'implémente pas scrollIntoView (appelé au montage par `select`/`popover`).
// Garde `typeof Element` : les tests d'outillage (scripts/) tournent en environnement
// node, où le DOM n'existe pas et où ce setup s'exécute quand même.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
