export const EVENT_TYPE_LABELS = {
  "triathlon-s":  "Triathlon S",
  "triathlon-m":  "Triathlon M",
  "triathlon-l":  "Triathlon L",
  "triathlon-xl": "Triathlon XL",
  "duathlon-xs":  "Duathlon XS",
  "duathlon-s":   "Duathlon S",
  "duathlon-m":   "Duathlon M",
  "duathlon-l":   "Duathlon L",
  "duathlon":     "Duathlon",
  "swimrun-s":    "SwimRun S",
  "swimrun-m":    "SwimRun M",
  "swimrun-l":    "SwimRun L",
  "swimrun":      "SwimRun",
  "aquathlon":    "Aquathlon",
  "aquarun":      "Aquarun",
  "bike-run":     "Bike & Run",
};

export const EVENT_TYPE_OPTIONS = Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => ({ value, label }));
