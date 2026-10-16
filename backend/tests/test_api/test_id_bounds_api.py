"""Ids beyond the PostgreSQL `integer` range are rejected by validation (#1557).

SQLite only overflows from 2**63, so these tests cannot reproduce the 500 seen
on PostgreSQL: they pin the 422 that now replaces it, and the OpenAPI guard
keeps every future id parameter under the same bound.
"""
import re

import pytest

from app.main import app
from app.schemas.ids import DB_ID_MAX

OUT_OF_RANGE = DB_ID_MAX + 1


@pytest.mark.parametrize(
    ("path", "params"),
    [
        (f"/api/v1/athletes/{OUT_OF_RANGE}", {}),
        (f"/api/v1/courses/{OUT_OF_RANGE}", {}),
        ("/api/v1/participations", {"course_id": OUT_OF_RANGE}),
        ("/api/v1/courses", {"id": OUT_OF_RANGE}),
        ("/api/v1/admin/courses/1/merge-impact", {"absorbed_id": OUT_OF_RANGE}),
        ("/api/v1/athletes/0", {}),
    ],
)
def test_out_of_range_id_is_a_422(client, path, params):
    response = client.get(path, params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/v1/volunteer-actions", {"athlete_id": OUT_OF_RANGE, "title": "t", "description": "d"}),
        ("/api/v1/admin/training-sessions", {"date": "2026-10-20", "group_ids": [OUT_OF_RANGE]}),
        ("/api/v1/admin/athletes/1/merge", {"absorbed_id": OUT_OF_RANGE}),
        ("/api/v1/admin/athletes/1/detach", {"participation_ids": [0]}),
    ],
)
def test_out_of_range_body_id_is_a_422(client, path, body):
    response = client.post(path, json=body)

    assert response.status_code == 422


def test_bounded_body_ids_stay_strict(client):
    response = client.post("/api/v1/admin/athletes/1/merge", json={"absorbed_id": True})

    assert response.status_code == 422


def test_largest_integer_id_still_reaches_the_route(client):
    response = client.get(f"/api/v1/athletes/{DB_ID_MAX}")

    assert response.status_code == 404


#: Ids that are not our primary keys: a GitHub Actions run id is already
#: beyond the int4 range, bounding it would reject every real run.
EXTERNAL_IDS = {("/api/v1/admin/batches/{run_id}/report", "run_id")}


def _is_id(path: str, name: str) -> bool:
    return (name == "id" or name.endswith("_id")) and (path, name) not in EXTERNAL_IDS


def _integer_schemas(schema: dict) -> list[dict]:
    return [s for s in [schema, *schema.get("anyOf", [])] if s.get("type") == "integer"]


def test_every_integer_id_parameter_carries_the_bound():
    unbounded = []
    for path, operations in app.openapi()["paths"].items():
        for method, operation in operations.items():
            for parameter in operation.get("parameters", []):
                if not _is_id(path, parameter["name"]):
                    continue
                for schema in _integer_schemas(parameter["schema"]):
                    if schema.get("minimum") != 1 or schema.get("maximum") != DB_ID_MAX:
                        unbounded.append(f"{method.upper()} {path} {parameter['name']}")

    assert unbounded == []


def test_external_ids_are_not_bounded():
    for path, name in EXTERNAL_IDS:
        parameters = app.openapi()["paths"][path]["get"]["parameters"]
        schema = next(p["schema"] for p in parameters if p["name"] == name)
        assert "maximum" not in schema


def _collect_refs(node, components: dict, seen: set[str]) -> None:
    if isinstance(node, dict):
        name = node.get("$ref", "").rsplit("/", 1)[-1]
        if name and name not in seen:
            seen.add(name)
            _collect_refs(components[name], components, seen)
        for value in node.values():
            _collect_refs(value, components, seen)
    elif isinstance(node, list):
        for value in node:
            _collect_refs(value, components, seen)


def _request_body_schemas() -> dict[str, dict]:
    spec = app.openapi()
    components = spec["components"]["schemas"]
    seen: set[str] = set()
    for operations in spec["paths"].values():
        for operation in operations.values():
            _collect_refs(operation.get("requestBody", {}), components, seen)
    return {name: components[name] for name in seen}


def _id_field_integers(field: str, schema: dict) -> list[dict]:
    # `athlete_id_a`, `course_id_b` (pairs) count as ids too.
    if re.search(r"(^|_)ids(_|$)", field):
        arrays = [s for s in [schema, *schema.get("anyOf", [])] if s.get("type") == "array"]
        return [i for s in arrays for i in _integer_schemas(s["items"])]
    if re.search(r"(^|_)id(_|$)", field):
        return _integer_schemas(schema)
    return []


def test_every_integer_id_in_a_request_body_carries_the_bound():
    unbounded = [
        f"{name}.{field}"
        for name, component in sorted(_request_body_schemas().items())
        for field, schema in component.get("properties", {}).items()
        for integer in _id_field_integers(field, schema)
        if integer.get("minimum") != 1 or integer.get("maximum") != DB_ID_MAX
    ]

    assert unbounded == []


@pytest.mark.parametrize("field", ["rank_overall", "rank_category", "rank_gender"])
def test_out_of_range_rank_is_a_422(client, field):
    body = {"athlete_name": "A", "event_name": "E", "event_type": "course-a-pied-10k", field: OUT_OF_RANGE}

    response = client.post("/api/v1/participations", json=body)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == field


def test_every_integer_rank_in_a_request_body_carries_the_bound():
    """Ranks land in `integer` columns too (#1574)."""
    ranks = [
        (f"{name}.{field}", integer)
        for name, component in sorted(_request_body_schemas().items())
        for field, schema in component.get("properties", {}).items()
        if field.startswith("rank_")
        for integer in _integer_schemas(schema)
    ]
    unbounded = [
        name for name, integer in ranks if integer.get("minimum") != 1 or integer.get("maximum") != DB_ID_MAX
    ]

    assert ranks
    assert unbounded == []
