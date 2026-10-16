from datetime import datetime

from pydantic import BaseModel

from app.schemas.utc_datetime import UtcDatetime


class _Model(BaseModel):
    at: UtcDatetime


def test_naive_utc_datetime_serializes_with_z_suffix():
    model = _Model(at=datetime(2026, 10, 16, 8, 30, 1, 123456))

    assert model.model_dump_json() == '{"at":"2026-10-16T08:30:01.123456Z"}'
    assert model.model_dump() == {"at": "2026-10-16T08:30:01.123456Z"}


def test_whole_second_keeps_isoformat_without_microseconds():
    assert _Model(at=datetime(2026, 10, 16, 8, 30)).model_dump_json() == '{"at":"2026-10-16T08:30:00Z"}'


def test_json_schema_stays_a_date_time_string():
    assert _Model.model_json_schema(mode="validation")["properties"]["at"] == {
        "format": "date-time",
        "title": "At",
        "type": "string",
    }
    assert _Model.model_json_schema(mode="serialization")["properties"]["at"] == {
        "title": "At",
        "type": "string",
    }
