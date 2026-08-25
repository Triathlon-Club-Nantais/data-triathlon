# Infrastructure Azure — base de production

La base PostgreSQL de production vit sur **Azure Database for PostgreSQL —
Flexible Server**, dans la souscription « Abonnement TCN ». C'est la seule
ressource Azure du périmètre `data-triathlon` : le backend tourne sur Render,
le frontend sur Vercel, et l'observabilité passe par les journaux de ces deux
plateformes. Ce fichier décrit ce qui est **déjà en place** ; les procédures
d'exploitation vivent dans [`ci-cd.md`](ci-cd.md).

Les identifiants sensibles (subscription id, tenant id, IDs de ressources)
ne sont pas commités : le dépôt est public. Se les procurer via
`az account show` et `az resource show`, ou dans le portail Azure.

## Ce qui existe

| Ressource | Valeur | Note |
|---|---|---|
| Resource group | `TCN_Data_BDD` | France Central |
| Serveur | `tcndatabdd` | Flexible Server, PG 18.x |
| FQDN | `tcndatabdd.postgres.database.azure.com` | résolution IPv4 |
| SKU | `Standard_B1ms` (Burstable) | tag `env=prd` |
| `max_connections` | `50` (défaut Azure pour ce SKU) | 15 réservées réplication/monitoring → **35 connexions utilisateur**. Pas de pooler PgBouncer intégré sur Burstable. Base du dimensionnement `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` (#585) |
| Stockage | 32 GiB Premium_LRS, auto-grow **désactivé** | 120 IOPS |
| Backup | 21 jours, **pas** de geo-redundant | |
| Haute disponibilité | Désactivée | mono-zone (zone 1) |
| Réseau | **Public network access = Enabled**, pas de VNet | firewall par règles |
| Auth | mot de passe seul (Azure AD auth désactivée) | admin : `data_admin_tcn` |
| TLS | `require_secure_transport=on`, `TLSv1.2` min | |

Une seule base applicative sur ce serveur (`postgres`) — les trois autres
(`azure_maintenance`, `azure_sys`) sont gérées par la plateforme.

## Ce que le réseau public change

Le serveur n'est **pas** dans un VNet privé : c'est le pare-feu applicatif du
serveur — une liste de règles CIDR — qui décide ce qui entre. C'est ce qui rend
possible l'ouverture *just-in-time* d'une IP par un runner GitHub Actions (voir
[`ci-cd.md`](ci-cd.md) §« Batches de production »).

Ce n'est pas un modèle qu'on ouvrirait par défaut sur une base d'adhérents,
mais il n'a rien de spécifique à cette feature — c'est la configuration en
place depuis la création du serveur, et Render s'y branche déjà par le même
mécanisme.

## Règles de firewall en place

Les valeurs de plages IP viennent de la documentation Render (« Outbound IPs »
pour Frankfurt) et **ne sont pas stables dans le temps** : Render peut
renuméroter, à charge pour l'exploitation de suivre. La vérité fait foi est
`az postgres flexible-server firewall-rule list -g TCN_Data_BDD -s tcndatabdd`.

| Nom | Portée | Objet |
|---|---|---|
| `render_inbound_p1` | plage /24 des sorties Render | backend prod |
| `render_indound_p2` | plage /24 des sorties Render | backend prod (typo dans le nom, à garder tant qu'aucune règle ne dépend d'elle par nom) |
| `ClientIPAddress_*` | IP unique | postes de dev, ajoutées à la volée |

**Convention pour les règles ajoutées par un workflow** : le nom porte le
`run_id` GitHub, préfixé par la source. Par exemple `gh-batch-<run_id>` pour
les ouvertures créées par `.github/workflows/batch.yml`. Cela rend chaque règle
imputable à une exécution précise et permet un nettoyage par filtre sans
ambiguïté :

```bash
az postgres flexible-server firewall-rule list -g TCN_Data_BDD -s tcndatabdd \
  --query "[?starts_with(name, 'gh-batch-')]" -o table
```

## Identités gérées pour GitHub Actions (#243)

Cinq objets Azure existent pour permettre au workflow `batch.yml` d'ouvrir et
refermer une règle firewall sur `tcndatabdd` sans porter de secret long-lived.
Tous sont dans le tier Entra ID Free — aucun coût, aucune ressource facturée.

| # | Type | Nom / ID | Portée |
|---|---|---|---|
| 1 | App registration | `gh-batch-data-triathlon` | tenant Entra ID de la souscription |
| 2 | Service principal | même `appId` que ci-dessus | tenant |
| 3 | Federated credential | `gh-batch-production` | subject `repo:Triathlon-Club-Nantais/data-triathlon:environment:batch-production` |
| 4 | Rôle custom | `PG Firewall Rule Writer (tcndatabdd)` | serveur `tcndatabdd` uniquement |
| 5 | Role assignment | rôle #4 → SP #2 | serveur `tcndatabdd` uniquement |

Le rôle custom porte trois actions et rien de plus :
`Microsoft.DBforPostgreSQL/flexibleServers/firewallRules/{read,write,delete}`.
Le service principal ne peut donc rien lire ni écrire dans la base, rien
toucher au réseau, au serveur, ou aux autres ressources du RG.

**Aucun secret client** n'est attaché à l'app registration : la
confiance passe uniquement par le federated credential, dont le `subject`
exige — chaîne pour chaîne — que le jeton GitHub vienne d'un job qui
déclare l'environment `batch-production` sur ce repo. Un fork malveillant, ou
un job sur un autre environment, n'obtient rien.

Les valeurs `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` et `AZURE_SUBSCRIPTION_ID`
sont posées comme secrets d'environment côté GitHub (voir
[`ci-cd.md`](ci-cd.md) § « Batches de production »). Elles se retrouvent à
tout moment via :

```bash
az ad app list --display-name gh-batch-data-triathlon --query "[].appId" -o tsv
az account show --query "{tenant:tenantId, subscription:id}" -o table
```

**Rollback complet.** Supprimer l'app registration met en cascade le SP, le
federated credential et le role assignment. Le rôle custom se supprime à
part.

```bash
az ad app delete --id <appId>
az role definition delete --name "PG Firewall Rule Writer (tcndatabdd)"
```

## Autres identités Azure

Les seules autres identités présentes sont celles des humains qui font
`az login`. Aucun autre *service principal* dédié `data-triathlon` n'existe.

## Ce qui n'est *pas* fait par Azure

- **Migrations SQL** — pilotées par Alembic depuis l'application (`uv run alembic upgrade head`).
- **Backups applicatifs** — les 21 jours de rétention Azure sont un filet, pas une politique de sauvegarde applicative.
- **Rotation du mot de passe admin** — manuelle, sans planification.
- **Réplique de lecture** — capacité disponible (`replicaCapacity: 5`) mais aucune réplique créée.
