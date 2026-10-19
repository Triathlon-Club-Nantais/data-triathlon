# Quickstart : vérifier le rattachement

1. Backend : `uv run pytest -m "not integration" tests/test_services/test_athlete_claims.py tests/test_api/test_athlete_claims_api.py tests/test_auth` ; migration : `uv run pytest tests/test_migrations.py`.
2. Frontend : `npm test -- AthleteSelection UserMenu AthleteClaimsTable providers`.
3. Sur la preview, avec un compte sans rôle :
   - ouvrir une fiche athlète, « C'est moi », confirmer : le menu du compte affiche « Demande en attente » ;
   - avec un compte porteur d'`athlete_claims:review`, `/admin/rattachements` : la demande est là, avec ses indices, la pastille du rail la compte ; valider ;
   - recharger avec le premier compte : le menu affiche la fiche, « Ma saison » la montre, « Choisir cet athlète » a disparu ; `/auth/me` rend `is_member: true` ;
   - « Me détacher de ma fiche » : la fiche disparaît du compte, la sélection locale est vide.
4. Journal d'administration : une ligne `athlete_claim.approve` signée par le responsable.
