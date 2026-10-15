import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { CourseBrief } from "@/lib/types";
import { CourseWeather } from "./CourseWeather";

const COURSE: CourseBrief = {
  id: 1,
  name: "Triathlon de Nantes",
  event_date: "2025-06-01",
  event_type: "triathlon-m",
  provider: "",
  source_url: "",
  is_relay: false,
};

describe("CourseWeather", () => {
  it("rend la météo du jour et crédite Open-Meteo par un lien", () => {
    render(
      <CourseWeather
        course={{ ...COURSE, weather_temperature_c: 18.04, weather_wind_kmh: 11.3, weather_precipitation_mm: 0.42 }}
      />,
    );

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://open-meteo.com/");
    expect(link).toHaveAttribute("title", expect.stringContaining("CC BY 4.0"));
    expect(link).toHaveTextContent("18 °C · vent 11 km/h · pluie 0,4 mm");
    expect(link).toHaveTextContent("Open-Meteo");
  });

  it("omet le vent et la pluie inconnus", () => {
    render(<CourseWeather course={{ ...COURSE, weather_temperature_c: -2 }} />);

    expect(screen.getByRole("link")).not.toHaveTextContent("vent");
  });

  it("ne rend rien sans météo", () => {
    const { container } = render(<CourseWeather course={COURSE} />);

    expect(container).toBeEmptyDOMElement();
  });
});
