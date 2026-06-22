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
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
