import { render } from "@testing-library/react";
import { ScrollArea } from "@base-ui/react/scroll-area";
import { describe, expect, it } from "vitest";

import { StableCSPProvider } from "./StableCSPProvider";

describe("StableCSPProvider (#570)", () => {
  it("signe le style de Base UI avec le nonce du premier rendu, pas celui d'un router.refresh()", () => {
    // `router.refresh()` rend à nouveau le layout racine avec le nonce d'une
    // nouvelle requête, que la CSP du document ne connaît pas : un popup ouvert
    // ensuite insérait son `<style>` signé par ce nonce, rapporté en violation.
    const { rerender } = render(<StableCSPProvider nonce="nonce-du-document">{null}</StableCSPProvider>);

    rerender(
      <StableCSPProvider nonce="nonce-du-refresh">
        <ScrollArea.Root>
          <ScrollArea.Viewport>contenu</ScrollArea.Viewport>
        </ScrollArea.Root>
      </StableCSPProvider>,
    );

    const style = document.head.querySelector<HTMLStyleElement>('style[data-href="base-ui-disable-scrollbar"]');
    expect(style?.nonce).toBe("nonce-du-document");
  });
});
