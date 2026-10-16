from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer


def _serialize_naive_utc(value: datetime) -> str:
    return f"{value.isoformat()}Z"


#: Suffixe `Z` : les colonnes sont des datetimes **naïfs en UTC** (`app/core/time.py`),
#: et un naïf sérialisé tel quel serait lu comme une heure locale par le client.
UtcDatetime = Annotated[datetime, PlainSerializer(_serialize_naive_utc)]
