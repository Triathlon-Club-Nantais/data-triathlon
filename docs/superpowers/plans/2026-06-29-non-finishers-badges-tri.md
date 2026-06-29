# Non-finishers : badges & tri en fin de tableau — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** Distinguer DNF/DNS/DSQ des finishers par un badge et les reléguer en fin du tableau `RaceFinishers`, tout en corrigeant la cause racine du faux « rang 0 / temps 00:00:00 » des non-partants TCN.

**Architecture :** Deux corrections backend dans les scrapers Klikego (préserver le temps des DNF/DSQ, ignorer les placeholders `00:00:00`/rang `0` de la page détail) ; côté frontend, une fonction de tri pure réutilisable + l'affichage d'un `StatusBadge` et d'un fond grisé dans `RaceFinishers`. Le champ `status` circule déjà de bout en bout (modèle → `ParticipationOut` → type TS), rien à ajouter à l'API ni de migration.

**Tech Stack :** Python 3.11, pytest (backend) ; Next.js 16, TypeScript, Vitest + React Testing Library (frontend). Aucune nouvelle dépendance.

## Global Constraints

- UI, commentaires et messages en **français** (avec accents).
- Tests unitaires **sans réseau** : ces tasks utilisent des données en dur, aucun marker `integration`.
- Conventional Commits (`fix:`, `feat:`, `test:`).
- Les temps restent des **strings** `"HH:MM:SS"`, normalisés via `app/scrapers/utils.normalize_time`.
- Constantes de statut : `STATUS_FINISHER = "finisher"`, `STATUS_DNF = "DNF"`, `STATUS_DNS = "DNS"`, `STATUS_DSQ = "DSQ"` (`app/scrapers/base.py`).
- Frontend : tokens couleur `--tcn-grey-400` (#b0aaa0), `--tcn-text-faint`, `--tcn-orange` déjà définis dans `app/globals.css`.

---

## File Structure

- **Modify `backend/app/scrapers/klikego_platform.py`** — `parse_data_row` : ne neutraliser le temps que pour les DNS ; DNF/DSQ conservent `officiel`.
- **Modify `backend/app/scrapers/klikego.py`** — `_parse_detail` : ignorer un `Temps Officiel` à `00:00:00` et un rang `0` (placeholders de la page détail).
- **Modify `backend/tests/test_klikego.py`** — tests des deux corrections.
- **Create `frontend/lib/utils/raceOrder.ts`** — `orderParticipations`, fonction de tri pure (finishers par rang, puis non-finishers groupés DNF → DSQ → DNS, par temps puis nom).
- **Create `frontend/lib/utils/raceOrder.test.ts`** — tests unitaires de la fonction de tri (sans DOM).
- **Modify `frontend/components/results/RaceFinishers.tsx`** — applique `orderParticipations`, affiche `StatusBadge` dans la colonne rang pour un non-finisher, fond grisé léger sur sa ligne.
- **Create `frontend/components/results/RaceFinishers.test.tsx`** — test RTL du rendu (badge + ordre).

---

## Task 1 : Backend — préserver le temps des DNF/DSQ (`parse_data_row`)

**Files :**
- Modify : `backend/app/scrapers/klikego_platform.py:86-97` (dict de retour de `parse_data_row`)
- Test : `backend/tests/test_klikego.py`

**Interfaces :**
- Consumes : `STATUS_DNS` (déjà importé dans le module).
- Produces : `parse_data_row(fields: list[str]) -> dict` — inchangé en signature ; `total_time` désormais conservé pour DNF/DSQ, vide pour DNS, rangs `None` pour tout non-finisher.

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
# backend/tests/test_klikego.py (ajout, près des autres tests parse_data_row)
def test_parse_data_row_dnf_keeps_time_when_present():
    # DNF ayant couru avant d'abandonner : officiel (idx 9) rempli
    fields = "12|false|DNF|DNF|MARTIN Paul|S2|M|CLUB|00:41:10|01:05:00||".split("|")
    r = parse_data_row(fields)
    assert r["status"] == "DNF"
    assert r["total_time"] == "01:05:00"   # temps conservé
    assert r["rank_overall"] is None       # jamais classé
    assert r["rank_category"] is None


def test_parse_data_row_dsq_keeps_time_when_present():
    fields = "34|false|DSQ|DSQ|DURAND Lea|S3|F|CLUB||01:12:30||".split("|")
    r = parse_data_row(fields)
    assert r["status"] == "DSQ"
    assert r["total_time"] == "01:12:30"
    assert r["rank_overall"] is None


def test_parse_data_row_dns_has_no_time():
    fields = "114|false|DNS|DNS|CHAUVET Romain|S4|M|TRIATHLON CLUB NANTAIS||00:00:00||".split("|")
    r = parse_data_row(fields)
    assert r["status"] == "DNS"
    assert r["total_time"] == ""           # un non-partant n'a pas de temps
    assert r["rank_overall"] is None
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run : `cd backend && pytest tests/test_klikego.py -k "keeps_time or dns_has_no_time" -v`
Expected : FAIL — `test_parse_data_row_dnf_keeps_time_when_present` échoue (`total_time == ""` car neutralisé pour tout statut).

- [ ] **Step 3 : Implémenter la correction**

Dans `backend/app/scrapers/klikego_platform.py`, remplacer la ligne `total_time` du dict de retour de `parse_data_row` :

```python
        "rank_overall": None if status else _parse_rank(clt),
        "rank_category": None if status else _parse_rank(cltcat),
        "total_time": "" if status == STATUS_DNS else normalize_time(officiel.strip()),
        "status": status,
```

(Seule la ligne `total_time` change : `if status` → `if status == STATUS_DNS`. Les finishers — `status == ""` — passent toujours par `normalize_time` ; DNF/DSQ aussi ; seul DNS est vidé.)

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run : `cd backend && pytest tests/test_klikego.py -k "parse_data_row" -v`
Expected : tous verts (les nouveaux + les anciens — l'ancien `test_parse_data_row_dnf_neutralises_rank_and_time` utilise un DNF sans `officiel`, son `total_time` reste `""`).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/scrapers/klikego_platform.py backend/tests/test_klikego.py
git commit -m "fix(scrapers): conserve le temps des DNF/DSQ, vide seulement les DNS"
```

---

## Task 2 : Backend — ignorer les placeholders de la page détail (`_parse_detail`)

**Files :**
- Modify : `backend/app/scrapers/klikego.py:90-110` (bloc `Temps Officiel` + `rank_map`)
- Test : `backend/tests/test_klikego.py`

**Interfaces :**
- Consumes : `_parse_detail(html: str, result: ScrapedResult, raw: dict)`, `ScrapedResult` (`app/scrapers/base.py`).
- Produces : `_parse_detail` ne pose plus `total_time = "00:00:00"` ni `rank_overall = 0`.

- [ ] **Step 1 : Écrire le test qui échoue**

```python
# backend/tests/test_klikego.py (ajout)
from app.scrapers.klikego import _parse_detail
from app.scrapers.base import ScrapedResult


def test_parse_detail_ignores_zero_placeholders():
    # Page détail d'un non-partant : temps officiel et rang à zéro (placeholders)
    html = """
    <div><div>Temps Officiel</div><div>00:00:00</div></div>
    <div><div>Classement Général</div><div>0</div></div>
    """
    r = ScrapedResult(source_url="https://x", provider="klikego")
    r.status = "DNS"
    _parse_detail(html, r, {})
    assert r.total_time == ""        # le 00:00:00 placeholder est ignoré
    assert r.rank_overall is None    # le rang 0 est ignoré
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd backend && pytest tests/test_klikego.py::test_parse_detail_ignores_zero_placeholders -v`
Expected : FAIL — `r.total_time == "00:00:00"` et `r.rank_overall == 0`.

- [ ] **Step 3 : Implémenter les garde-fous**

Dans `backend/app/scrapers/klikego.py`, bloc `Temps Officiel` (≈ l.90-95), ajouter le filtre `00:00:00` :

```python
        if text == "Temps Officiel":
            val_div = div.find_next_sibling("div")
            if val_div:
                t = normalize_time(val_div.get_text(strip=True))
                if t and t != "00:00:00":
                    result.total_time = t
```

Puis dans la boucle `rank_map` (≈ l.97-110), ignorer un rang `0` :

```python
        for label, field in rank_map.items():
            if text_low == label:
                val_div = div.find_next_sibling("div")
                if val_div:
                    rank_text = val_div.get_text(strip=True)
                    m = re.match(r"(\d+)", rank_text)
                    if m and int(m.group(1)) > 0:
                        rank = int(m.group(1))
                        if field == "overall":
                            result.rank_overall = rank
                        elif field == "category":
                            result.rank_category = rank
                        else:
                            result.rank_gender = rank
```

(Le seul changement : `if m:` → `if m and int(m.group(1)) > 0:`.)

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run : `cd backend && pytest tests/test_klikego.py -k "parse_detail" -v`
Expected : tous verts (le nouveau test + les tests `_parse_detail` existants avec de vrais temps/rangs, inchangés).

- [ ] **Step 5 : Vérifier la non-régression Klikego complète**

Run : `cd backend && pytest tests/test_klikego.py -v`
Expected : tous verts.

- [ ] **Step 6 : Commit**

```bash
git add backend/app/scrapers/klikego.py backend/tests/test_klikego.py
git commit -m "fix(scrapers): ignore les placeholders 00:00:00 / rang 0 de la page détail"
```

---

## Task 3 : Frontend — fonction de tri pure `orderParticipations`

**Files :**
- Create : `frontend/lib/utils/raceOrder.ts`
- Test : `frontend/lib/utils/raceOrder.test.ts`

**Interfaces :**
- Consumes : type `Participation` (`@/lib/types`).
- Produces : `orderParticipations(parts: Participation[]): Participation[]` — nouveau tableau trié : finishers d'abord (par `rank_overall` croissant, `null` après, puis nom) ; puis non-finishers groupés **DNF → DSQ → DNS** ; au sein d'un groupe, par temps croissant (sans temps / `00:00:00` en fin) puis nom. `isNonFinisher(status: string | null | undefined): boolean` — exporté pour réutilisation par le composant.

- [ ] **Step 1 : Écrire les tests qui échouent**

```ts
// frontend/lib/utils/raceOrder.test.ts
import { describe, it, expect } from "vitest";
import { orderParticipations, isNonFinisher } from "./raceOrder";
import type { Participation } from "@/lib/types";

function p(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: { id: over.id, nom: over.athlete?.nom ?? "X", prenom: over.athlete?.prenom ?? "Y", gender: "M", club: null },
    course: { id: 1, event_name: "C", event_date: null, event_type: null },
    club: null,
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: over.total_time ?? null,
    status: over.status ?? "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
  } as Participation;
}

describe("orderParticipations", () => {
  it("place les finishers avant les non-finishers, par rang", () => {
    const out = orderParticipations([
      p({ id: 3, status: "DNS" }),
      p({ id: 1, status: "finisher", rank_overall: 2 }),
      p({ id: 2, status: "finisher", rank_overall: 1 }),
    ]);
    expect(out.map((x) => x.id)).toEqual([2, 1, 3]);
  });

  it("ordonne les groupes DNF → DSQ → DNS", () => {
    const out = orderParticipations([
      p({ id: 1, status: "DNS" }),
      p({ id: 2, status: "DSQ" }),
      p({ id: 3, status: "DNF" }),
    ]);
    expect(out.map((x) => x.id)).toEqual([3, 2, 1]);
  });

  it("dans un groupe, trie par temps croissant puis place les sans-temps en fin", () => {
    const out = orderParticipations([
      p({ id: 1, status: "DNF", total_time: null, athlete: { nom: "ZZZ" } as never }),
      p({ id: 2, status: "DNF", total_time: "01:10:00" }),
      p({ id: 3, status: "DNF", total_time: "00:50:00" }),
    ]);
    expect(out.map((x) => x.id)).toEqual([3, 2, 1]);
  });

  it("traite 00:00:00 comme une absence de temps", () => {
    const out = orderParticipations([
      p({ id: 1, status: "DNS", total_time: "00:00:00", athlete: { nom: "BBB" } as never }),
      p({ id: 2, status: "DNS", total_time: null, athlete: { nom: "AAA" } as never }),
    ]);
    // tous deux sans temps → tri alphabétique : AAA (2) avant BBB (1)
    expect(out.map((x) => x.id)).toEqual([2, 1]);
  });
});

describe("isNonFinisher", () => {
  it("reconnaît DNF/DNS/DSQ (toute casse) et rejette finisher/vide", () => {
    expect(isNonFinisher("DNF")).toBe(true);
    expect(isNonFinisher("dns")).toBe(true);
    expect(isNonFinisher("DSQ")).toBe(true);
    expect(isNonFinisher("finisher")).toBe(false);
    expect(isNonFinisher("")).toBe(false);
    expect(isNonFinisher(null)).toBe(false);
  });
});
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run : `cd frontend && npx vitest run lib/utils/raceOrder.test.ts`
Expected : FAIL — `Cannot find module './raceOrder'`.

- [ ] **Step 3 : Implémenter `raceOrder.ts`**

```ts
// frontend/lib/utils/raceOrder.ts
import type { Participation } from "@/lib/types";

const NON_FINISHER = new Set(["DNF", "DNS", "DSQ"]);

/** Vrai si le statut est un non-finisher porteur de sigle (DNF/DNS/DSQ). */
export function isNonFinisher(status: string | null | undefined): boolean {
  return NON_FINISHER.has((status ?? "").toUpperCase());
}

// Rang de groupe : finishers d'abord, puis DNF, DSQ, DNS.
function groupRank(p: Participation): number {
  const s = (p.status ?? "").toUpperCase();
  if (s === "DNF") return 1;
  if (s === "DSQ") return 2;
  if (s === "DNS") return 3;
  return 0; // finisher, vide ou inconnu
}

// Secondes d'un temps "HH:MM:SS". Vide, invalide ou "00:00:00" = aucune valeur.
function timeSeconds(t: string | null): number {
  if (!t || t === "00:00:00") return Number.POSITIVE_INFINITY;
  const parts = t.split(":").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return Number.POSITIVE_INFINITY;
  return parts[0] * 3600 + parts[1] * 60 + parts[2];
}

function fullName(p: Participation): string {
  return `${p.athlete?.nom ?? ""} ${p.athlete?.prenom ?? ""}`.trim().toLowerCase();
}

/**
 * Trie les participations pour l'affichage : finishers d'abord (par rang
 * croissant, les non classés après), puis non-finishers groupés DNF → DSQ → DNS.
 * Au sein d'un groupe : par temps croissant (sans temps en fin), puis par nom.
 */
export function orderParticipations(parts: Participation[]): Participation[] {
  return [...parts].sort((a, b) => {
    const ga = groupRank(a);
    const gb = groupRank(b);
    if (ga !== gb) return ga - gb;

    if (ga === 0) {
      const ra = a.rank_overall ?? Number.POSITIVE_INFINITY;
      const rb = b.rank_overall ?? Number.POSITIVE_INFINITY;
      if (ra !== rb) return ra - rb;
      return fullName(a).localeCompare(fullName(b));
    }

    const ta = timeSeconds(a.total_time);
    const tb = timeSeconds(b.total_time);
    if (ta !== tb) return ta - tb;
    return fullName(a).localeCompare(fullName(b));
  });
}
```

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run : `cd frontend && npx vitest run lib/utils/raceOrder.test.ts`
Expected : tous verts.

- [ ] **Step 5 : Commit**

```bash
git add frontend/lib/utils/raceOrder.ts frontend/lib/utils/raceOrder.test.ts
git commit -m "feat(frontend): tri des participations (finishers puis DNF/DSQ/DNS)"
```

---

## Task 4 : Frontend — badges & fond grisé dans `RaceFinishers`

**Files :**
- Modify : `frontend/components/results/RaceFinishers.tsx`
- Test : `frontend/components/results/RaceFinishers.test.tsx`

**Interfaces :**
- Consumes : `orderParticipations`, `isNonFinisher` (Task 3) ; `StatusBadge` (`@/components/results/StatusBadge`) ; `PlaceBadge`, `Card`, `SegmentedControl` (`@/components/tcn`).
- Produces : composant `RaceFinishers` (props inchangées : `{ participations: Participation[]; tcnCount: number }`).

- [ ] **Step 1 : Écrire le test qui échoue**

```tsx
// frontend/components/results/RaceFinishers.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Participation } from "@/lib/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { RaceFinishers } from "./RaceFinishers";

function p(over: Partial<Participation> & { id: number; nom: string }): Participation {
  return {
    id: over.id,
    athlete: { id: over.id, nom: over.nom, prenom: "T", gender: "M", club: null },
    course: { id: 1, event_name: "C", event_date: null, event_type: null },
    club: over.club ?? null,
    category: "S4",
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: over.total_time ?? null,
    status: over.status ?? "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
  } as Participation;
}

describe("RaceFinishers", () => {
  const data = [
    p({ id: 1, nom: "FINISHER", status: "finisher", rank_overall: 1, total_time: "00:55:00" }),
    p({ id: 2, nom: "DNSGUY", status: "DNS" }),
    p({ id: 3, nom: "DNFGUY", status: "DNF", total_time: "01:10:00" }),
  ];

  it("affiche un badge DNS/DNF pour les non-finishers", () => {
    render(<RaceFinishers participations={data} tcnCount={0} />);
    expect(screen.getByText("DNS")).toBeInTheDocument();
    expect(screen.getByText("DNF")).toBeInTheDocument();
  });

  it("relègue les non-finishers après les finishers (DNF avant DNS)", () => {
    render(<RaceFinishers participations={data} tcnCount={0} />);
    const rows = screen.getAllByRole("button", { name: /Voir le profil/ });
    const labels = rows.map((r) => r.getAttribute("aria-label"));
    expect(labels).toEqual([
      "Voir le profil de FINISHER T",
      "Voir le profil de DNFGUY T",
      "Voir le profil de DNSGUY T",
    ]);
  });
});
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd frontend && npx vitest run components/results/RaceFinishers.test.tsx`
Expected : FAIL — aucun badge « DNS »/« DNF » rendu (colonne rang affiche `0`/`—`), et l'ordre n'est pas garanti.

- [ ] **Step 3 : Modifier les imports de `RaceFinishers.tsx`**

En tête de `frontend/components/results/RaceFinishers.tsx`, ajouter sous les imports existants :

```tsx
import { StatusBadge } from "@/components/results/StatusBadge";
import { orderParticipations, isNonFinisher } from "@/lib/utils/raceOrder";
```

- [ ] **Step 4 : Appliquer le tri après le filtre**

Remplacer la ligne (≈ l.26) :

```tsx
  const rows = filter === "tcn" ? participations.filter((p) => isTCN(p.club)) : participations;
```

par :

```tsx
  const filtered = filter === "tcn" ? participations.filter((p) => isTCN(p.club)) : participations;
  const rows = orderParticipations(filtered);
```

- [ ] **Step 5 : Badge dans la colonne rang + fond grisé sur la ligne**

Dans le `rows.map((p) => { ... })`, calculer le flag non-finisher après `const own = isTCN(p.club);` :

```tsx
            const own = isTCN(p.club);
            const nf = isNonFinisher(p.status);
```

Remplacer la cellule rang (la `<div>` contenant `PlaceBadge`, ≈ l.70) par :

```tsx
                <div>
                  {nf ? (
                    <StatusBadge status={p.status} />
                  ) : p.rank_overall != null ? (
                    <PlaceBadge place={p.rank_overall} style={{ minWidth: 28, fontSize: 16 }} />
                  ) : (
                    <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
                  )}
                </div>
```

Dans le `style` de la `<div>` ligne (celle avec `role="button"`, ≈ l.68), ajouter le fond grisé léger pour les non-finishers — remplacer :

```tsx
                style={{ display: "grid", gridTemplateColumns: FCOLS, gap: "0 12px", alignItems: "center", padding: "12px 22px", borderBottom: "1px solid var(--tcn-border-faint)", borderLeft: `3px solid ${own ? "var(--tcn-orange)" : "transparent"}` }}
```

par :

```tsx
                style={{ display: "grid", gridTemplateColumns: FCOLS, gap: "0 12px", alignItems: "center", padding: "12px 22px", borderBottom: "1px solid var(--tcn-border-faint)", borderLeft: `3px solid ${own ? "var(--tcn-orange)" : "transparent"}`, background: nf ? "color-mix(in srgb, var(--tcn-grey-400) 15%, transparent)" : undefined }}
```

- [ ] **Step 6 : Lancer le test ciblé, vérifier le succès**

Run : `cd frontend && npx vitest run components/results/RaceFinishers.test.tsx`
Expected : 2 passed.

- [ ] **Step 7 : Lint + typecheck + suite frontend**

Run : `cd frontend && npm run lint && npx vitest run`
Expected : lint OK, tous les tests verts.

- [ ] **Step 8 : Commit**

```bash
git add frontend/components/results/RaceFinishers.tsx frontend/components/results/RaceFinishers.test.tsx
git commit -m "feat(frontend): badge et relégation des non-finishers dans RaceFinishers"
```

---

## Task 5 : Validation globale

**Files :** aucun (vérification).

- [ ] **Step 1 : Suite backend sans réseau**

Run : `cd backend && pytest -m "not integration"`
Expected : tous verts.

- [ ] **Step 2 : Lint backend**

Run : `cd backend && ruff check app/scrapers/ tests/test_klikego.py`
Expected : `All checks passed!`

- [ ] **Step 3 : Build frontend**

Run : `cd frontend && npm run build`
Expected : build prod OK (strict TS + RSC).

- [ ] **Step 4 : Commit final si corrections de lint**

```bash
git add -A && git commit -m "chore: lint badges & tri des non-finishers"
```

---

## Self-Review

**1. Couverture de la spec :**
- A1 (préserver temps DNF/DSQ, vider DNS) → Task 1. ✓
- A2 (ignorer placeholders 00:00:00 / rang 0) → Task 2. ✓
- B1 (tri finishers puis DNF→DSQ→DNS, par temps puis nom) → Task 3 (`orderParticipations`) + Task 4 (application). ✓
- B2 (StatusBadge dans la colonne rang) → Task 4, Step 5. ✓
- B3 (colonne temps inchangée, `—` si absent) → inchangée, vérifiée par le rendu existant. ✓
- B4 (fond grisé léger) → Task 4, Step 5 (`color-mix` sur `--tcn-grey-400`). ✓
- Tests backend & frontend → Tasks 1-4. ✓

**2. Scan placeholders :** aucun TODO/TBD ; chaque step de code montre le code complet.

**3. Cohérence des types :** `orderParticipations(Participation[]) -> Participation[]` et `isNonFinisher(string|null|undefined) -> boolean` réutilisés à l'identique entre Task 3 et Task 4. `parse_data_row -> dict` et `_parse_detail(html, result, raw)` conformes aux signatures existantes. `StatusBadge` consommé avec sa prop `status` documentée.

**Risque à surveiller :** `color-mix` CSS — supporté par les navigateurs cibles de Next 16 ; si un test de rendu en jsdom devait s'en plaindre, il n'inspecte pas la couleur (les assertions portent sur le texte et l'ordre), donc sans impact.
