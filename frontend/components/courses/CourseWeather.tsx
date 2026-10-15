import { MetaPill } from "@/components/tcn";
import type { CourseBrief } from "@/lib/types";

const whole = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const tenth = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

/**
 * Météo du jour de course (#1370), écrite hors ligne par `weather-courses`.
 * Open-Meteo est crédité à l'affichage, comme l'exige sa licence CC BY 4.0.
 */
export function CourseWeather({ course }: { course: CourseBrief }) {
  const { weather_temperature_c: temperature, weather_wind_kmh: wind, weather_precipitation_mm: rain } = course;
  if (temperature == null) return null;
  const parts = [`${whole.format(temperature)} °C`];
  if (wind != null) parts.push(`vent ${whole.format(wind)} km/h`);
  if (rain != null) parts.push(`pluie ${tenth.format(rain)} mm`);
  return (
    <MetaPill
      label="Météo"
      href="https://open-meteo.com/"
      title="Moyennes du jour de course. Données Open-Meteo.com, licence CC BY 4.0."
    >
      {parts.join(" · ")}
      <span style={{ color: "var(--tcn-text-faint)", fontWeight: 400 }}>Open-Meteo</span>
    </MetaPill>
  );
}
