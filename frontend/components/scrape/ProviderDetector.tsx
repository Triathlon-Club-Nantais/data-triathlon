"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { useDebounce } from "@/hooks/useDebounce";
import { useProviders } from "@/lib/queries/batches";
import { providerLabel } from "@/lib/constants";

type Detected = { provider: string; supported: boolean };

/** Hauteur du verdict, réservée avant qu'il n'existe.
 *
 *  Le badge apparaissait et disparaissait au rythme du débounce, et déplaçait
 *  le bouton d'import pendant la frappe (#492, ACT-6). */
const HAUTEUR_VERDICT = 22;

/**
 * La ligne sous le champ URL : **un seul** verdict, à un seul endroit.
 *
 * Trois états, jamais deux en même temps — au repos, les chronométreurs pris en
 * charge ; après une frappe, le fournisseur reconnu ou l'absence de
 * reconnaissance, avec sa sortie. Il y en avait trois simultanés avant ce lot
 * (badge rouge, alerte jaune, bouton principal actif qui promettait l'inverse),
 * et rien du tout **avant** de coller.
 */
export function ProviderDetector({
  url,
  onDetected,
  onSaisieManuelle,
}: {
  url: string;
  /** Relaie chaque détection au parent — `null` tant qu'aucune n'est connue —
   *  pour qu'un écran puisse réagir sans dupliquer l'appel `detectProvider`. */
  onDetected?: (detected: Detected | null) => void;
  /** La sortie offerte sur adresse non reconnue. Absent, rien n'est proposé :
   *  c'est le cas quand une participation vient d'être saisie à la main, et que
   *  réinviter à la saisir contredirait l'accusé de réception. */
  onSaisieManuelle?: () => void;
}) {
  const debounced = useDebounce(url, 400);
  const [detected, setDetected] = useState<Detected | null>(null);

  useEffect(() => {
    if (!debounced || !debounced.startsWith("http")) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDetected(null);
      onDetected?.(null);
      return;
    }
    let cancelled = false;
    apiClient
      .detectProvider(debounced)
      .then((r) => {
        if (cancelled) return;
        // Le support est tranché par le registre backend, jamais par une liste
        // tenue ici : la précédente avait divergé et affichait « Non supporté »
        // sur Competitor, RaceResult et Chronoplace, pourtant importables.
        setDetected(r);
        onDetected?.(r);
      })
      .catch(() => {
        if (cancelled) return;
        setDetected(null);
        onDetected?.(null);
      });
    return () => {
      cancelled = true;
    };
    // `onDetected` n'est délibérément pas dans les dépendances : le rendre
    // stable serait à la charge de chaque appelant, pour un callback qui ne
    // lit jamais son ancienne valeur.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  if (!url) return <ChronometreursConnus />;

  return (
    <div
      data-verdict=""
      style={{
        minHeight: HAUTEUR_VERDICT,
        display: "flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 8,
        fontSize: 14,
        fontWeight: 500,
      }}
    >
      {/* Deux états, pas trois : `is_supported` et `detect_provider` sont
          adossés au même `get_provider(url)` côté registre, donc `supported`
          ⟺ `provider !== ""`. Nommer un fournisseur non supporté donnerait
          « Non supporté (Source) », le repli de `providerLabel` — un faux nom
          pour un état que l'API ne rend pas. */}
      {detected?.supported ? (
        <span style={{ color: "var(--tcn-text-body)" }}>
          <span aria-hidden="true">✓ </span>
          Chronométreur reconnu : {providerLabel(detected.provider)}
        </span>
      ) : detected ? (
        <>
          <span style={{ color: "var(--tcn-danger-text, var(--tcn-danger-border))" }}>
            Aucun chronométreur ne reconnaît cette adresse.
          </span>
          {onSaisieManuelle && (
            <button type="button" className="tcn-lien-action" onClick={onSaisieManuelle}>
              Saisir à la main
            </button>
          )}
        </>
      ) : null}
    </div>
  );
}

/** Ce que l'app sait lire, dit **avant** qu'on colle quoi que ce soit.
 *
 *  La liste vient du registre backend (`GET /scrape/providers`) : le front en
 *  a déjà tenu une à la main, et elle avait divergé. Muette tant qu'elle n'a
 *  pas répondu, et sur échec : c'est un repère, pas un prérequis au collage. */
function ChronometreursConnus() {
  const { data: providers } = useProviders();
  if (!providers?.length) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 6, fontSize: 13 }}>
      <span style={{ color: "var(--tcn-text-muted)", fontWeight: 500 }}>
        Chronométreurs pris en charge :
      </span>
      {providers.map((p) => (
        <span
          key={p}
          style={{
            padding: "2px 8px",
            borderRadius: 999,
            background: "var(--tcn-surface-sunk)",
            color: "var(--tcn-text-body)",
            fontWeight: 600,
          }}
        >
          {providerLabel(p)}
        </span>
      ))}
    </div>
  );
}
