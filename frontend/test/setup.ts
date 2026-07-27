import "@testing-library/jest-dom/vitest";

// jsdom ne fournit pas ResizeObserver, requis par certaines primitives (cmdk…).
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// jsdom n'implémente pas scrollIntoView (utilisé par cmdk au montage).
// Garde `typeof Element` : les tests d'outillage (scripts/) tournent en environnement
// node, où le DOM n'existe pas et où ce setup s'exécute quand même.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
