import { describe, expect, it } from "vitest";
import type { Participation } from "@/lib/types";
import { CARD_HEIGHT, CARD_WIDTH, drawResultCard, resultCardModel } from "./result-card";

function participation(extra: Partial<Participation> = {}): Participation {
  return {
    id: 5,
    athlete: { id: 42, prenom: "Léa", nom: "Martin" },
    course: {
      id: 9, name: "Triathlon de Nantes", event_date: "2026-06-07", event_type: "triathlon-m",
      provider: "klikego", source_url: "", is_relay: false,
    },
    club: "TRIATHLON CLUB NANTAIS",
    is_tcn: true,
    category: "SEF",
    bib_number: "120",
    rank_overall: 12,
    rank_category: 2,
    rank_gender: 3,
    total_time: "2:10:05",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    teammates: [{ id: 77, prenom: "Tiers", nom: "Nommé" }],
    ...extra,
  } as Participation;
}

describe("resultCardModel (#1371)", () => {
  it("carries the athlete's own line: event, date, discipline, time and ranks", () => {
    const model = resultCardModel(participation());

    expect(model).toEqual({
      club: "Triathlon Club Nantais",
      event: "Triathlon de Nantes",
      date: "7 juin 2026",
      discipline: "Triathlon M",
      athlete: "Léa Martin",
      result: "2:10:05",
      ranks: ["12e au scratch", "2e en catégorie SEF"],
    });
  });

  it("says the status instead of time and ranks for a non-finisher", () => {
    const model = resultCardModel(participation({ status: "DNF", total_time: null, rank_overall: null }));

    expect(model.result).toBe("Abandon");
    expect(model.ranks).toEqual([]);
  });

  it("names nobody else", () => {
    expect(JSON.stringify(resultCardModel(participation()))).not.toMatch(/Tiers|Nommé|120/);
  });
});

describe("drawResultCard (#1371)", () => {
  it("draws the model's texts, and only them, on a 1080×1350 card", () => {
    const texts: string[] = [];
    const ctx = new Proxy(
      { fillText: (text: string) => void texts.push(text), measureText: () => ({ width: 100 }) },
      {
        get: (target, key) => (key in target ? target[key as keyof typeof target] : () => ({ addColorStop: () => {} })),
        set: () => true,
      },
    ) as unknown as CanvasRenderingContext2D;
    const model = resultCardModel(participation());

    drawResultCard(ctx, model, { display: "Anton", body: "Barlow" });

    expect([CARD_WIDTH, CARD_HEIGHT]).toEqual([1080, 1350]);
    expect(texts).toEqual([
      "TRIATHLON CLUB NANTAIS",
      "Triathlon de Nantes",
      "Triathlon M · 7 juin 2026",
      "Léa Martin",
      "2:10:05",
      "12e au scratch",
      "2e en catégorie SEF",
    ]);
  });
});
