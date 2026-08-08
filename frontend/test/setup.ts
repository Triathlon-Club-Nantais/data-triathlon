import "@testing-library/jest-dom/vitest";

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
