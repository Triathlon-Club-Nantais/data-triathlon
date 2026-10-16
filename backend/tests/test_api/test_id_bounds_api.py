"""Ids beyond the PostgreSQL `integer` range are rejected by validation (#1557).

SQLite only overflows from 2**63, so these tests cannot reproduce the 500 seen
on PostgreSQL: they pin the 422 that now replaces it, and the OpenAPI guard
keeps every future id parameter under the same bound.
"""
import pytest

from app.api.deps import DB_ID_MAX
from app.main import app

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


def test_largest_integer_id_still_reaches_the_route(client):
    response = client.get(f"/api/v1/athletes/{DB_ID_MAX}")

    assert response.status_code == 404


def _is_id(name: str) -> bool:
    return name == "id" or name.endswith("_id")


def _integer_schemas(schema: dict) -> list[dict]:
    return [s for s in [schema, *schema.get("anyOf", [])] if s.get("type") == "integer"]


def test_every_integer_id_parameter_carries_the_bound():
    unbounded = []
    for path, operations in app.openapi()["paths"].items():
        for method, operation in operations.items():
            for parameter in operation.get("parameters", []):
                if not _is_id(parameter["name"]):
                    continue
                for schema in _integer_schemas(parameter["schema"]):
                    if schema.get("minimum") != 1 or schema.get("maximum") != DB_ID_MAX:
                        unbounded.append(f"{method.upper()} {path} {parameter['name']}")

    assert unbounded == []
