from typing import Annotated

from annotated_types import Ge, Le

#: Borne haute des identifiants : les clés primaires sont des `integer`
#: PostgreSQL, et au delà la requête lève une `DataError` (500) au lieu d'une
#: 422 (#1557, #1567). `DbId` s'emploie en chemin, en requête
#: (`DbId | None = Query(None)`, ou `Annotated[DbId, Query()]` si obligatoire :
#: `DbId = Query(...)` perd la borne) et sur les champs des corps JSON
#: (`DbId`, `list[DbId]`). Tout identifiant de clé primaire doit le porter
#: (garde : `tests/test_api/test_id_bounds_api.py`).
DB_ID_MAX = 2_147_483_647
DbId = Annotated[int, Ge(1), Le(DB_ID_MAX)]
