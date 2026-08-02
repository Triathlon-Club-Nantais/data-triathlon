"""Socle d'authentification SSO (#114).

`api → services/auth → repositories` : ce paquet porte la transaction et la
politique, les repositories seuls construisent les requêtes, et le router se
borne à traduire en HTTP.

Le sous-paquet est nommé `idp/` et non `providers/` : « provider » désigne déjà
un **chronométreur** dans tout le dépôt (`PendingProvider`, `--provider`,
`PROVIDER_LABELS`, `GET /scrape/detect`), et employer le même mot pour un
fournisseur d'identité créerait un second sens et un second `registry.py`
homonyme.
"""
