import { scaleLinear } from "d3-scale";
import { buildTicks, formatTickLabel } from "@/lib/utils/histogram-ticks";

export function Histogram({
  bars,
  max,
  startSec,
  bucketSec,
}: {
  bars: number[];
  max: number;
  startSec: number;
  bucketSec: number;
}) {
  const W = 900;
  const H = 240; // +20px par rapport à l'ancien 220 pour loger les labels X
  const top = 20;
  const bottom = 190;
  const left = 46;
  const usableW = W - left - 10;
  const barGap = usableW / bars.length;
  const barW = Math.max(4, barGap * 0.72);
  const yTicks = 5;

  // Domaine [0, max] → pixel [bottom, top] (plus de finishers = plus haut).
  // Repli constant si max=0 : scaleLinear diviserait par un domaine nul.
  const yScale = max > 0 ? scaleLinear().domain([0, max]).range([bottom, top]) : (value: number) => bottom;

  const endSec = startSec + bars.length * bucketSec;
  const xTicks = bars.length > 0 ? buildTicks(startSec, endSec) : [];
  const secToX = (sec: number) => left + ((sec - startSec) / bucketSec) * barGap;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {Array.from({ length: yTicks + 1 }, (_, i) => {
        const v = Math.round((max / yTicks) * i);
        const y = bottom - (i / yTicks) * (bottom - top);
        return (
          <g key={i}>
            <line x1={left - 6} y1={y} x2={W - 10} y2={y} stroke="var(--tcn-border-faint)" />
            <text x={left - 14} y={y + 4} textAnchor="end" fontSize="11" fill="var(--tcn-text-faint)" fontFamily="Barlow">{v}</text>
          </g>
        );
      })}
      {bars.map((c, i) => {
        const y = yScale(c);
        return <rect key={i} x={left + i * barGap} y={y} width={barW} height={bottom - y} rx="2" fill="var(--tcn-orange)" />;
      })}
      {xTicks.map((tickSec) => {
        const x = secToX(tickSec);
        return (
          <g key={tickSec}>
            <line x1={x} y1={top} x2={x} y2={bottom} stroke="var(--tcn-border-faint)" />
            <text x={x} y={bottom + 16} textAnchor="middle" fontSize="11" fill="var(--tcn-text-faint)" fontFamily="Barlow">{formatTickLabel(tickSec)}</text>
          </g>
        );
      })}
    </svg>
  );
}
