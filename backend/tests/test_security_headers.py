"""En-têtes de sécurité des réponses de l'API (#396, constat A05-2 + A02-1).

Ce qui est éprouvé ici est une propriété de **toute** réponse, pas d'une route :
d'où le 404 aux côtés du 200, seul moyen de distinguer un middleware d'un
en-tête posé à la main dans un handler.
"""


def test_toute_reponse_porte_les_en_tetes_de_securite(client):
    resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert resp.headers["x-frame-options"] == "DENY"


def test_une_reponse_d_erreur_les_porte_aussi(client):
    resp = client.get("/api/v1/route-qui-n-existe-pas")

    assert resp.status_code == 404
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert resp.headers["x-frame-options"] == "DENY"


def test_hsts_pose_sur_une_requete_https(client):
    # Render termine TLS et annonce le schéma d'origine par `X-Forwarded-Proto` ;
    # `ProxyHeadersMiddleware` le recopie dans `scope["scheme"]`.
    resp = client.get("/api/v1/health", headers={"X-Forwarded-Proto": "https"})

    assert resp.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"


def test_pas_de_hsts_sur_une_requete_en_clair(client):
    """RFC 6797 §8.1 : l'en-tête reçu hors transport sûr doit être ignoré.

    Le poser quand même serait donc inoffensif mais mensonger — et masquerait,
    en développement, le fait que la production le doit à `X-Forwarded-Proto`.
    """
    resp = client.get("/api/v1/health")

    assert "strict-transport-security" not in resp.headers
