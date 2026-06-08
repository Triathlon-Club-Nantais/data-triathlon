from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class ScrapedResult:
    source_url: str
    provider: str
    athlete_name: str = ""
    athlete_firstname: str = ""
    club: str = ""
    category: str = ""
    gender: str = ""
    bib_number: str = ""
    event_name: str = ""
    event_date: date | None = None
    event_type: str = ""
    rank_overall: int | None = None
    rank_category: int | None = None
    rank_gender: int | None = None
    total_time: str = ""
    swim_time: str = ""
    t1_time: str = ""
    bike_time: str = ""
    t2_time: str = ""
    run_time: str = ""
    is_relay: bool = False
    raw_data: dict[str, Any] = field(default_factory=dict)
