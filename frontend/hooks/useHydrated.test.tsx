import { act } from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { useHydrated } from "./useHydrated";

function Probe({ seen }: { seen: boolean[] }) {
  const hydrated = useHydrated();
  seen.push(hydrated);
  return <span>{hydrated ? "client" : "server"}</span>;
}

describe("useHydrated", () => {
  it("is false on the server render", () => {
    expect(renderToString(<Probe seen={[]} />)).toContain("server");
  });

  it("is false on the first client render that hydrates, then true", async () => {
    const container = document.createElement("div");
    container.innerHTML = renderToString(<Probe seen={[]} />);
    document.body.appendChild(container);
    const seen: boolean[] = [];

    await act(async () => {
      hydrateRoot(container, <Probe seen={seen} />);
    });

    expect(seen[0]).toBe(false);
    expect(seen.at(-1)).toBe(true);
    expect(container.textContent).toBe("client");
  });
});
