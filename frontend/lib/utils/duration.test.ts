import { describe, expect, it } from "vitest";
import { formatDuration, parseDuration } from "./duration";

describe("parseDuration", () => {
  it.each([
    ["42,3", 423],
    ["42.3", 423],
    ["42", 420],
    [" 7:42,3 ", 4623],
    ["7:42", 4620],
    ["1:02:05", 37250],
    ["0,1", 1],
  ])("lit %s", (text, expected) => expect(parseDuration(text)).toBe(expected));

  it.each(["", "abc", "0", "7:75", "42,35", "1:2:05", "1:60:00", "25:00:00", "-3"])(
    "refuse %s",
    (text) => expect(parseDuration(text)).toBeNull(),
  );
});

describe("formatDuration", () => {
  it.each([
    [423, "42,3 s"],
    [420, "42 s"],
    [4623, "7:42,3"],
    [4620, "7:42"],
    [37250, "1:02:05"],
  ])("affiche %i", (tenths, expected) => expect(formatDuration(tenths)).toBe(expected));
});
