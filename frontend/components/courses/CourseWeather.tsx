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
  // `+ 0` efface le zéro négatif : `signDisplay` manque avant Firefox 116.
  const parts = [`${whole.format(Math.round(temperature) + 0)} °C`];
  if (wind != null) parts.push(`vent ${whole.format(wind)} km/h`);
  if (rain != null) parts.push(`pluie ${tenth.format(rain)} mm`);
  const values = parts.join(" · ");
  return (
    <MetaPill
      label="Météo"
      href="https://open-meteo.com/"
      className="tcn-cible-tactile"
      title="Température et vent moyens, pluie cumulée sur le jour de course. Données Open-Meteo.com, licence CC BY 4.0 (nouvel onglet)."
      ariaLabel={`Météo du jour de course : ${values}. Données Open-Meteo, nouvel onglet`}
    >
      {values}
      <span style={{ color: "var(--tcn-text-faint)", fontWeight: 400 }}>Open-Meteo</span>
      <span aria-hidden="true">↗</span>
    </MetaPill>
  );
}
