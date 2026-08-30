"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { captureEvent } from "@/lib/posthog";
import { Card, Input, Button, Alert, PendingBadge, AnnonceStatut } from "@/components/tcn";
import { apiClient, type DetectedProvider } from "@/lib/api/client";
import { eventTypeLabel } from "@/lib/constants";
import { eventTypeColor } from "@/lib/sport-colors";
import { formatEventName } from "@/lib/utils/event";
import { isHttpUrl } from "@/lib/utils/url";
import { useSaveParticipation } from "@/lib/queries/participations";
import { useImportStream } from "@/hooks/useImportStream";
import { ProviderDetector, ID_VERDICT } from "./ProviderDetector";
import { ManualResultForm } from "./ManualResultForm";
import type { ImportedCourse, Participation, ScrapedPreview } from "@/lib/types";

export function TcnScrapeForm() {
  const [url, setUrl] = useState("");
  const [manual, setManual] = useState(false);
  // Une ligne immobile pendant des minutes ne distingue pas « ça travaille »
  // de « c'est figé » (#491, ACT-4). La minuterie tient cette promesse même
  // sous `prefers-reduced-motion`, qui gèle l'indicateur animé.
  const [secondes, setSecondes] = useState(0);
  // Le résultat saisi à la main, gardé après l'enregistrement : c'est lui que
  // l'accusé de réception affiche (ACT-1).
  const [saved, setSaved] = useState<Participation | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  // Détection client (GET /scrape/detect), indépendante de toute tentative
  // d'import : elle permet d'avertir avant même le clic sur « Enregistrer les
  // résultats », plutôt que d'attendre l'échec réel du scrape.
  const [providerUnsupported, setProviderUnsupported] = useState(false);
  // Portée de l'import (#698) : le contrôle ne s'affiche que si `fanout` est
  // vrai, et `singleHeat` est réinitialisé au défaut serveur à chaque
  // nouvelle détection — le front ne recalcule jamais ce défaut lui-même,
  // même principe que `providerUnsupported`.
  const [fanout, setFanout] = useState(false);
  const [singleHeat, setSingleHeat] = useState(true);
  const handleProviderDetected = useCallback(
    (detected: DetectedProvider | null) => {
      setProviderUnsupported(detected !== null && !detected.supported);
      setFanout(detected?.fanout ?? false);
      setSingleHeat(detected?.default_single_heat ?? true);
    },
    [],
  );
  const champRef = useRef<HTMLInputElement>(null);
  const reportedRef = useRef<string | null>(null);
  // L'URL réellement **soumise**. La garde de signalement portait sur `url`,
  // l'état vivant du champ : corriger son adresse après un échec relançait
  // toast, télémétrie et `reportPendingProvider` à **chaque frappe**, avec
  // autant de chaînes tronquées jamais soumises — exactement la pollution de
  // `pending-providers` que ce lot vient fermer.
  const soumiseRef = useRef<string>("");
  const refreshedRef = useRef<string | null>(null);
  const router = useRouter();

  const save = useSaveParticipation();
  const importStream = useImportStream();
  const {
    phase, error, errorStatus, retryAfter, running, imported, updated, skipped, total, progress,
    cached, message, courses, heatIndex, heatsScrapingTotal, heatLabel, detailDone, detailTotal,
    heatsEnumerated, heatsImported, heatsCached, heatsFailed, failures,
  } = importStream.state;

  // Un import qui ramène des séries en échec n'est pas un import réussi : le
  // dire en vert ferait passer 3 séries perdues sur 12 pour un plein succès
  // (#491, ACT-3).
  const partiel = phase === "done" && failures.length > 0;

  // `!partiel` en tête : toutes les séries servies par le cache TTL **plus** une
  // en échec reste un cas atteignable, et l'alerte « déjà enregistrés » y
  // escamotait la liste des manques — le silence même que ce lot corrige.
  const isDuplicate =
    phase === "done" && !partiel && (cached || (imported === 0 && updated === 0 && skipped > 0));

  // Trois causes, trois gestes (#491, ACT-2). `errorStatus` vaut `null` quand
  // le flux s'est ouvert avant d'annoncer l'échec : c'est le **seul** cas où
  // la page est en cause, donc le seul qui vaille une saisie manuelle et un
  // signalement au back-office. Un 429 ou un 500 signalés en « fournisseur
  // non supporté » polluaient `pending-providers` de liens parfaitement lisibles.
  const motifEchec =
    phase !== "error"
      ? null
      : errorStatus === 429
        ? "plafond"
        : errorStatus === 0 || (errorStatus !== null && errorStatus >= 500)
          ? "service"
          : "lecture";

  // Défense en profondeur alignée sur le backend (`ScrapeRequest.url: HttpUrl`,
  // 422 dès la porte, cf. `schemas/scrape.py`) : on filtre côté UI pour ne pas
  // envoyer une requête qu'on sait invalide, et pour rendre la contrainte
  // visible avant clic. `isHttpUrl` accepte `http(s)` et rejette `javascript:`,
  // `data:`, `ftp:`, chaînes vides et non-URL.
  const trimmed = url.trim();
  const urlIsValid = isHttpUrl(trimmed);
  const showUrlError = trimmed.length > 0 && !urlIsValid;

  // Effacer puis rendre la main au champ : sans le focus, il faut le viser une
  // seconde fois au doigt pour recoller (ACT-5).
  const effacer = useCallback(() => {
    setUrl("");
    setSaved(null);
    champRef.current?.focus();
  }, []);

  // `readText()` demande une permission que Safari accorde par une invite, et
  // que Firefox refuse tout net : on le dit plutôt que d'avaler l'échec sur un
  // bouton qui n'aurait alors aucun effet visible.
  const coller = useCallback(async () => {
    try {
      const texte = (await navigator.clipboard.readText()).trim();
      if (!texte) return;
      setUrl(texte);
      setSaved(null);
      champRef.current?.focus();
    } catch {
      toast.message("Impossible de lire le presse-papiers", {
        description: "Collez l'adresse directement dans le champ (appui long, ou Ctrl+V).",
      });
    }
  }, []);

  const submit = useCallback(() => {
    const v = url.trim();
    if (!v || running) return;
    if (!isHttpUrl(v)) return;
    // La touche Entrée ne contourne pas le bouton désactivé : sans cette garde,
    // le clavier lance l'import que le verdict vient d'exclure (ACT-6).
    if (providerUnsupported) return;
    reportedRef.current = null;
    refreshedRef.current = null;
    soumiseRef.current = v;
    setManual(false);
    setSecondes(0);
    setSaved(null);
    captureEvent("results_import_started", { url: v });
    importStream.start(v, singleHeat);
  }, [url, running, providerUnsupported, singleHeat, importStream]);

  // Sur échec de lecture **avéré** : signaler le fournisseur + proposer la
  // saisie manuelle. Un plafond de débit ou un service muet ne disent rien de
  // l'URL, et n'ouvrent donc ni l'un ni l'autre.
  useEffect(() => {
    const soumise = soumiseRef.current;
    if (motifEchec !== "lecture" || !soumise || reportedRef.current === soumise) return;
    reportedRef.current = soumise;
    toast.error(error ?? "Import impossible");
    apiClient.reportPendingProvider(soumise).catch(() => {});
    setManual(true);
    captureEvent("results_import_failed", { error_message: error ?? "Import impossible" });
  }, [motifEchec, error]);

  // Les deux autres causes ne se taisent pas pour autant : le toast reste, la
  // télémétrie aussi, seuls le signalement et la saisie manuelle sautent.
  useEffect(() => {
    const soumise = soumiseRef.current;
    if (motifEchec === null || motifEchec === "lecture" || reportedRef.current === soumise) return;
    reportedRef.current = soumise;
    toast.error(error ?? "Import impossible");
    captureEvent("results_import_failed", { error_message: error ?? "Import impossible" });
  }, [motifEchec, error]);

  // Après un import réel, invalider le cache RSC de la page pour que la carte
  // « Derniers résultats enregistrés » (rendue côté serveur dans /ajouter) reflète
  // la nouvelle épreuve sans F5 manuel. Sur doublon (cache TTL frais), rien à
  // rafraîchir. Le ref garde l'URL déjà rafraîchie, réinitialisé au submit
  // suivant — sinon un re-render sur `phase === "done"` rappellerait refresh.
  useEffect(() => {
    if (phase !== "done" || isDuplicate) return;
    if (refreshedRef.current === url) return;
    refreshedRef.current = url;
    router.refresh();
    // Même garde `refreshedRef` que router.refresh() ci-dessus : un seul tir
    // par import, malgré les 3 dépendances ajoutées pour satisfaire
    // exhaustive-deps.
    captureEvent("results_import_completed", {
      imported_count: imported,
      skipped_count: skipped,
      course_count: courses.length,
    });
  }, [phase, isDuplicate, url, router, imported, skipped, courses.length]);

  // Une horloge, deux usages : le temps passé sur l'import en cours, et le
  // temps écoulé depuis un refus pour plafond de débit. Sans le second, le
  // « compte à rebours » restait figé sur sa valeur d'origine — `running` étant
  // déjà `false` quand l'alerte s'affiche —, et « Réessayez dans 3 minutes »
  // l'affirmait encore dix minutes plus tard.
  // Décompte du plafond de débit : `Retry-After` est un instantané, il fond
  // avec le temps qui passe.
  const attenteRestante = Math.max(0, (retryAfter ?? 0) - secondes);
  const compteEnCours = running || (motifEchec === "plafond" && retryAfter !== null);
  useEffect(() => {
    if (!compteEnCours) return;
    const debut = Date.now();
    const id = setInterval(() => {
      const ecoulees = Math.floor((Date.now() - debut) / 1000);
      setSecondes(ecoulees);
      // Le décompte fini, plus rien à compter : ne pas re-rendre l'écran une
      // fois par seconde sur une alerte que personne ne referme.
      if (!running && retryAfter !== null && ecoulees >= retryAfter) clearInterval(id);
    }, 1000);
    return () => clearInterval(id);
  }, [compteEnCours, running, retryAfter]);

  // Fermer l'onglet coupe la SSE et arrête l'import à mi-course : le dire
  // avant, plutôt que de laisser une épreuve à moitié importée en base.
  useEffect(() => {
    if (!running) return;
    const garde = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", garde);
    return () => window.removeEventListener("beforeunload", garde);
  }, [running]);


  // `cancel()` coupe la SSE, pas la transaction déjà partie côté serveur : les
  // participants enregistrés avant le clic restent en base. Le taire ferait
  // croire à une annulation propre, démentie au prochain chargement.
  const annuler = useCallback(() => {
    importStream.cancel();
    toast.message("Import interrompu", {
      description: "Les résultats déjà enregistrés sont conservés. Relancez l'import pour reprendre le reste.",
    });
  }, [importStream]);

  const persist = useCallback(
    async (data: Partial<ScrapedPreview>) => {
      try {
        // La `Participation` rendue porte son `id` et son épreuve : c'est ce qui
        // permet à l'accusé de réception de mener au résultat créé plutôt que de
        // refermer la carte sur un toast fugace (ACT-1).
        setSaveError(null);
        setSaved(await save.mutateAsync(data));
        setManual(false);
      } catch (e) {
        // Persistant, comme le succès : le formulaire reste rempli sous les
        // yeux, un toast qui s'efface ne dirait pas quoi refaire (ACT-1).
        setSaveError((e as Error).message);
      }
    },
    [save],
  );

  const inputStatus = showUrlError
    ? "error"
    : isDuplicate
      ? "error"
      : phase === "error"
        ? "warning"
        : running
          ? "active"
          : "default";

  return (
    <>
      <Card padding={32} style={{ marginBottom: 22 }}>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", marginBottom: 5 }}>
          Collez ici l&apos;adresse des résultats de votre épreuve
        </div>
        <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 500, marginBottom: 18 }}>
          Le lien vers la page de résultats officielle du chronométreur (PDF, site web…)
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 260 }}>
            <Input
              ref={champRef}
              value={url}
              status={inputStatus}
              // Repartir d'une adresse, c'est repartir d'un import : l'accusé
              // de réception de la saisie précédente s'efface, sans quoi il
              // masquerait le préavis « fournisseur non reconnu » de la
              // nouvelle et refermerait la porte de la saisie manuelle.
              onChange={(e) => { setUrl(e.target.value); setSaved(null); }}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder="https://www.klikego.com/…"
              type="url"
              inputMode="url"
              // Une URL n'est ni capitalisée, ni corrigée par le correcteur, et
              // la touche d'action du clavier mobile lance l'import (ACT-5).
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              enterKeyHint="go"
              // Le placeholder n'est pas un nom accessible, et il disparaît dès
              // que « Coller » remplit le champ.
              aria-label="Adresse des résultats"
              aria-invalid={showUrlError || undefined}
              aria-describedby={showUrlError ? "scrape-url-error" : undefined}
              actions={
                url ? (
                  <ActionChamp label="Effacer l'adresse" onClick={effacer}>
                    ×
                  </ActionChamp>
                ) : (
                  <ActionChamp label="Coller l'adresse" onClick={coller}>
                    <span style={{ fontSize: 13, fontWeight: 700 }}>Coller</span>
                  </ActionChamp>
                )
              }
            />
            {showUrlError && (
              <div
                id="scrape-url-error"
                role="alert"
                style={{ marginTop: 6, fontSize: 13, color: "var(--tcn-danger-text)", fontWeight: 500 }}
              >
                Cette adresse n&apos;est pas une URL valide (elle doit commencer par http:// ou https://).
              </div>
            )}
            <div style={{ marginTop: 8 }}>
              <ProviderDetector
                url={url}
                onDetected={handleProviderDetected}
                // Deux cas où la sortie manuelle ne s'offre pas : une
                // participation vient d'être saisie, et la réinviter
                // contredirait l'accusé de réception ; ou un import tourne, et
                // ouvrir le formulaire par-dessus sa barre de progression
                // proposerait deux gestes concurrents sur la même épreuve.
                onSaisieManuelle={saved || running ? undefined : () => setManual(true)}
              />
            </div>
            {/* `<fieldset>`/`<legend>` plutôt qu'un `role="radiogroup"` porté par
                une div et nommé par `aria-label` : ce dernier est **invisible**
                aux yeux, et l'utilisateur voyait deux options sans savoir de
                quoi elles étaient les deux faces. Patron déjà en place dans
                `PermissionGrid`. Le `role="group"` implicite du `<fieldset>`
                remplace `radiogroup` : les deux boutons restent groupés par la
                frontière du fieldset et par leur `name` commun. */}
            {fanout && (
              <fieldset
                style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4, fontSize: 14 }}
              >
                <legend style={{ fontWeight: 600, color: "var(--tcn-text-body)", marginBottom: 2 }}>
                  Portée de l&apos;import
                </legend>
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input
                    type="radio"
                    name="scrape-scope"
                    checked={singleHeat}
                    onChange={() => setSingleHeat(true)}
                    disabled={running}
                  />
                  Importer uniquement cette page
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input
                    type="radio"
                    name="scrape-scope"
                    checked={!singleHeat}
                    onChange={() => setSingleHeat(false)}
                    disabled={running}
                  />
                  Importer tout l&apos;événement (toutes ses épreuves)
                </label>
              </fieldset>
            )}
          </div>
          {/* `providerUnsupported` dans `disabled` : le bouton restait actif et
              promettait le contraire du verdict affiché sous le champ (ACT-6).
              `aria-describedby` porte la raison du blocage jusqu'à qui atteint
              le bouton sans voir la ligne (WCAG 4.1.3). */}
          <Button size="lg" onClick={submit} disabled={running || !urlIsValid || providerUnsupported} aria-describedby={url ? ID_VERDICT : undefined} iconRight={<span>→</span>} style={{ borderRadius: "var(--tcn-radius-xl)" }}>
            {running ? "Import en cours…" : "Enregistrer les résultats"}
          </Button>
        </div>

        {(phase === "scraping" || phase === "saving") && (
          <div style={{ marginTop: 14 }}>
            <ImportBar
              phase={phase}
              progress={progress}
              total={total}
              imported={imported}
              skipped={skipped}
              message={message}
              heatIndex={heatIndex}
              heatsScrapingTotal={heatsScrapingTotal}
              heatLabel={heatLabel}
              detailDone={detailDone}
              detailTotal={detailTotal}
              secondes={secondes}
              onAnnuler={annuler}
            />
          </div>
        )}

        {phase === "done" && !isDuplicate && (
          <div style={{ marginTop: 14 }}>
            <Alert
              status={partiel ? "warning" : "success"}
              title={
                partiel
                  ? `Import partiel : ${failures.length} série${failures.length > 1 ? "s" : ""} sur ${heatsEnumerated} manque${failures.length > 1 ? "nt" : ""}`
                  : "Résultats enregistrés avec succès !"
              }
              action={
                partiel ? (
                  <Button variant="secondary" size="sm" onClick={submit}>
                    Relancer l&apos;import
                  </Button>
                ) : null
              }
            >
              <BilanChiffres
                imported={imported}
                updated={updated}
                skipped={skipped}
                heatsEnumerated={heatsEnumerated}
                heatsImported={heatsImported}
                heatsCached={heatsCached}
                heatsFailed={heatsFailed}
              />
              {failures.length > 0 && (
                <>
                  <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                    {failures.slice(0, MAX_ECHECS_LISTES).map((f, i) => (
                      <li key={`${f.heat_slug}-${i}`}>
                        Série « {f.heat_slug} » : {causeSerie(f.reason)}.
                      </li>
                    ))}
                  </ul>
                  {failures.length > MAX_ECHECS_LISTES && (
                    <div style={{ marginTop: 4 }}>
                      … et {failures.length - MAX_ECHECS_LISTES} autres séries.
                    </div>
                  )}
                </>
              )}
              <CourseNavigator courses={courses} />
            </Alert>
          </div>
        )}
        {isDuplicate && (
          <div style={{ marginTop: 14 }}>
            <Alert status="error" title="Résultats déjà enregistrés">
              Ces résultats ont déjà été ajoutés. Les statistiques sont à jour ({skipped} participants en base).
              <CourseNavigator courses={courses} />
            </Alert>
          </div>
        )}
        {motifEchec === "plafond" && (
          <div style={{ marginTop: 14 }}>
            <Alert status="warning" title="Trop d'imports dans l'heure">
              {attenteRestante > 0
                ? `Réessayez dans ${formatAttente(attenteRestante)}.`
                : "Vous pouvez réessayer maintenant."}{" "}
              Cette limite protège les sites des chronométreurs ; vos imports précédents sont bien enregistrés.
            </Alert>
          </div>
        )}
        {motifEchec === "service" && (
          <div style={{ marginTop: 14 }}>
            <Alert
              status="warning"
              title="Le service n'a pas répondu"
              action={<Button variant="secondary" size="sm" onClick={submit}>Réessayer</Button>}
            >
              L&apos;import n&apos;a pas pu aboutir — connexion interrompue ou service momentanément indisponible.
              L&apos;adresse que vous avez collée n&apos;est pas en cause.
            </Alert>
          </div>
        )}
        {/* Cette alerte ne dit plus que l'**échec de lecture avéré** : le
            « fournisseur non reconnu » avant tentative est le verdict de la
            ligne sous le champ, et il ne se dit qu'une fois (ACT-6).
            `!saved` : une fois la saisie manuelle enregistrée, réinviter à
            saisir à la main contredirait l'accusé de réception juste dessous. */}
        {!saved && motifEchec === "lecture" && (
          <div style={{ marginTop: 14 }}>
            <Alert
              status="warning"
              title="Impossible d'importer automatiquement"
              action={<Button variant="secondary" size="sm" onClick={() => setManual(true)}>Saisir à la main</Button>}
            >
              {error ?? "Le lien fourni n'a pas pu être lu."}{" "}
              Vous pouvez saisir votre participation manuellement.
            </Alert>
          </div>
        )}
      </Card>

      {manual && (
        <Card padding={30} style={{ border: "1.5px solid var(--tcn-warning-border)", marginBottom: 22 }}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", marginBottom: 6 }}>Saisie manuelle de votre participation</div>
          <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", marginBottom: 22 }}>Complétez les champs ci-dessous. Votre participation sera vérifiée par un bénévole du club avant d&apos;apparaître dans les résultats.</div>
          {saveError && (
            <div style={{ marginBottom: 18 }}>
              <Alert status="error" title="Impossible d'enregistrer votre participation">
                {saveError} Vos réponses sont conservées ci-dessous : corrigez ce qui doit
                l&apos;être, puis renvoyez le formulaire.
              </Alert>
            </div>
          )}
          <ManualResultForm defaultUrl={url} onSubmit={persist} submitting={save.isPending} />
        </Card>
      )}

      {saved && (
        <Card padding={30} style={{ marginBottom: 22 }}>
          {/* Le formulaire est démonté au moment où cette carte apparaît : sans
              région live, rien n'est annoncé et le focus retombe sur `body`
              (WCAG 4.1.3, #477). */}
          <AnnonceStatut texte="Votre participation est enregistrée, en attente de validation par un bénévole du club." />
          <Alert status="success" title="Merci ! Votre participation est en attente de validation.">
            <div style={{ marginBottom: 10 }}>
              <PendingBadge />
            </div>
            Un bénévole du club la vérifie, en général sous quelques jours. Elle apparaîtra dans
            les résultats et les statistiques du club dès qu&apos;elle sera validée.
            <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap" }}>
              <PrimaryLink href={`/courses/${saved.course.id}/participations/${saved.id}`}>
                Voir ma participation <span aria-hidden="true">→</span>
              </PrimaryLink>
              <Button
                variant="secondary"
                onClick={() => { setSaved(null); setManual(true); }}
              >
                Saisir une autre participation
              </Button>
            </div>
          </Alert>
        </Card>
      )}
    </>
  );
}

/** Bouton posé dans le champ URL : 44px de cible tactile, nom accessible
 *  explicite — « × » et « Coller » ne disent rien à l'oreille (ACT-5). */
function ActionChamp({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className="tcn-action-champ"
      aria-label={label}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

/** Au-delà, l'alerte devient un mur de puces : sur un fan-out à 12 séries
 *  toutes perdues, la liste occupait tout le bandeau. */
const MAX_ECHECS_LISTES = 5;

/** Ce qu'une série perdue dit à qui la lit.
 *
 *  `reason` arrive du backend en `str(exc)` (`import_service`, huit scrapers) :
 *  anglais, technique, parfois une URL brute — donc irrecevable tel quel dans
 *  une copie utilisateur (Principe I). On n'en garde que ce qui change le geste :
 *  réessayer plus tard, ou renoncer. Le texte d'origine reste dans les logs
 *  backend, qui sont sa place. */
function causeSerie(reason: string): string {
  if (/timeout|timed out/i.test(reason)) return "le chronométreur n'a pas répondu à temps";
  if (/\b(429|5\d\d)\b/.test(reason)) return "le chronométreur était indisponible";
  if (/\b40[34]\b/.test(reason)) return "la page n'existe plus";
  return "la page n'a pas pu être lue";
}

/** « 3 minutes » ou « moins d'une minute » — le décompte du plafond de débit.
 *  Les secondes n'y apportent rien sur une attente qui se compte en minutes, et
 *  un « 179 s » qui défile donnerait envie de rester à regarder. */
function formatAttente(secondes: number): string {
  const minutes = Math.ceil(secondes / 60);
  if (minutes <= 1) return "moins d'une minute";
  return `${minutes} minutes`;
}

/** « 45 s », « 1 min 5 s » — le temps déjà passé sur l'import en cours. */
function formatDuree(secondes: number): string {
  if (secondes < 60) return `${secondes} s`;
  return `${Math.floor(secondes / 60)} min ${secondes % 60} s`;
}

/** Les cinq chiffres du bilan (#491, ACT-3).
 *
 *  L'écran n'en rendait que deux : un import qui ne faisait que **mettre à
 *  jour** s'annonçait « 0 résultat ajouté », et les séries perdues d'un fan-out
 *  ne se lisaient nulle part. Chaque chiffre porte son propre `<span>` : c'est
 *  ce qui le rend lisible un par un, à l'œil comme au test. */
function BilanChiffres({
  imported,
  updated,
  skipped,
  heatsEnumerated,
  heatsImported,
  heatsCached,
  heatsFailed,
}: {
  imported: number;
  updated: number;
  skipped: number;
  heatsEnumerated: number;
  heatsImported: number;
  heatsCached: number;
  heatsFailed: number;
}) {
  return (
    <>
      <div>
        <span>{imported} résultat{imported > 1 ? "s" : ""} ajouté{imported > 1 ? "s" : ""}</span>
        {" · "}
        <span>{updated} mis à jour</span>
        {" · "}
        <span>{skipped} déjà présent{skipped > 1 ? "s" : ""}</span>
      </div>
      {heatsEnumerated > 0 && (
        <div style={{ marginTop: 4 }}>
          <span>
            {heatsImported} série{heatsImported > 1 ? "s" : ""} importée{heatsImported > 1 ? "s" : ""} sur {heatsEnumerated}
          </span>
          {heatsCached > 0 ? <span>{` · ${heatsCached} déjà à jour`}</span> : null}
          {heatsFailed > 0 ? <span>{` · ${heatsFailed} en échec`}</span> : null}
        </div>
      )}
    </>
  );
}

/** Bouton d'action TCN rendu en `<a>` : mêmes styles que `Button variant="primary"`,
 *  mais navigable au clavier et par les crawlers. Utilisé pour aller vers /courses/{id}
 *  depuis les alertes de fin d'import (#135).
 *
 *  Les styles étaient recopiés à la main tant qu'ils vivaient en ligne dans
 *  `tcn/Button` ; depuis #299 ils sont en classes, donc il suffit de les porter —
 *  et le focus, le survol et le blanc à 3,68:1 se corrigent ici du même coup.
 */
function PrimaryLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="tcn-btn tcn-btn--md tcn-btn--primary">
      {children}
    </Link>
  );
}

/** Point d'entrée vers les résultats d'un import.
 *
 *  - 0 course : rien (import vide ou en erreur).
 *  - 1 course : un unique bouton primary, filant droit vers `/courses/{id}`.
 *  - N courses (heats Klikego, Wiclax, RaceResult multi-listes) : un sélecteur
 *    pour choisir la course + un bouton `Voir les résultats` — plus lisible
 *    qu'une grille de N boutons quand N dépasse 3-4.
 */
function CourseNavigator({ courses }: { courses: ImportedCourse[] }) {
  // Sélection brute : ce que l'utilisateur a cliqué (vide au premier rendu).
  // La valeur d'affichage est **dérivée** ci-dessous — pas d'`useEffect`
  // pour la synchroniser à `courses`, car un setState dans effect cascade
  // le rendu et déclenche l'erreur `react-hooks/set-state-in-effect`.
  const [selectedId, setSelectedId] = useState<string>("");

  if (courses.length === 0) return null;

  // Fallback à la 1re course tant que l'utilisateur n'a rien choisi, **et**
  // si sa sélection ne fait plus partie des courses (scénario improbable :
  // le SSE re-yield une phase `done` sur une nouvelle épreuve).
  const stillPresent = courses.some((c) => String(c.id) === selectedId);
  const effectiveId = stillPresent ? selectedId : String(courses[0].id);

  if (courses.length === 1) {
    const c = courses[0];
    return (
      <div style={{ marginTop: 12 }}>
        <PrimaryLink href={`/courses/${c.id}`}>
          Voir les résultats de « {formatEventName(c.name, Boolean(c.is_relay))} » <span aria-hidden="true">→</span>
        </PrimaryLink>
      </div>
    );
  }

  const selectedCourse = courses.find((c) => String(c.id) === effectiveId) ?? courses[0];

  return (
    <div style={{ marginTop: 12 }}>
      <div
        style={{
          fontFamily: "var(--tcn-font-cond)",
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: "var(--tcn-eyebrow-tracking)",
          textTransform: "uppercase",
          color: "var(--tcn-orange)",
          marginBottom: 8,
        }}
      >
        {courses.length} épreuve{courses.length > 1 ? "s" : ""} importée{courses.length > 1 ? "s" : ""}
      </div>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 10,
        }}
      >
        <CourseSelectField
          courses={courses}
          selectedId={effectiveId}
          selectedCourse={selectedCourse}
          onChange={setSelectedId}
        />
        <PrimaryLink href={`/courses/${effectiveId}`}>
          Voir les résultats <span aria-hidden="true">→</span>
        </PrimaryLink>
      </div>
    </div>
  );
}

/** `<select>` natif restylé TCN : bord épais, pastille de discipline colorée
 *  à gauche, chevron custom, focus visible orange. Prend la variante
 *  « Input » (bg `--tcn-fill`, radius XL, transition sur `border-color`) pour
 *  rester cohérent avec le champ URL juste au-dessus.
 */
function CourseSelectField({
  courses,
  selectedId,
  selectedCourse,
  onChange,
}: {
  courses: ImportedCourse[];
  selectedId: string;
  selectedCourse: ImportedCourse;
  onChange: (id: string) => void;
}) {
  const [focused, setFocused] = useState(false);
  const dotColor = eventTypeColor(selectedCourse.event_type);
  return (
    <label
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        minWidth: 320,
        flex: "1 1 320px",
        padding: "12px 42px 12px 16px",
        background: "var(--tcn-fill)",
        border: `1.5px solid ${focused ? "var(--tcn-orange)" : "var(--tcn-border)"}`,
        borderRadius: "var(--tcn-radius-xl)",
        transition: "border-color var(--tcn-dur-fast)",
        cursor: "pointer",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          flex: "none",
          width: 10,
          height: 10,
          borderRadius: 999,
          background: dotColor,
          boxShadow: "0 0 0 3px color-mix(in oklch, " + dotColor + " 15%, transparent)",
        }}
      />
      <span
        style={{
          flex: 1,
          minWidth: 0,
          fontFamily: "var(--tcn-font-body)",
          fontSize: 15,
          fontWeight: 600,
          color: "var(--tcn-ink)",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {formatEventName(selectedCourse.name, Boolean(selectedCourse.is_relay))}
        <span style={{ color: "var(--tcn-text-muted)", fontWeight: 500 }}>
          {" · "}
          {eventTypeLabel(selectedCourse.event_type)}
        </span>
      </span>
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          right: 16,
          top: "50%",
          transform: "translateY(-50%)",
          color: "var(--tcn-text-muted)",
          fontSize: 12,
          fontWeight: 800,
          pointerEvents: "none",
        }}
      >
        ▾
      </span>
      <select
        aria-label="Choisir l'épreuve à consulter"
        value={selectedId}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          opacity: 0,
          cursor: "pointer",
          border: "none",
          background: "transparent",
          appearance: "none",
        }}
      >
        {courses.map((c) => (
          <option key={c.id} value={String(c.id)}>
            {formatEventName(c.name, Boolean(c.is_relay))} · {eventTypeLabel(c.event_type)}
          </option>
        ))}
      </select>
    </label>
  );
}

function ImportBar({
  phase,
  progress,
  total,
  imported,
  skipped,
  message,
  heatIndex,
  heatsScrapingTotal,
  heatLabel,
  detailDone,
  detailTotal,
  secondes,
  onAnnuler,
}: {
  phase: string;
  progress: number;
  total: number;
  imported: number;
  skipped: number;
  message: string;
  heatIndex: number;
  heatsScrapingTotal: number;
  heatLabel: string;
  detailDone: number;
  detailTotal: number;
  secondes: number;
  onAnnuler: () => void;
}) {
  const pct = total > 0 ? Math.round((progress / total) * 100) : 0;
  // Fan-out Klikego (#156) : le backend émet un événement `scraping` par heat
  // avec `heat_index/heats_total/heat_label`. Sur un provider mono-course, ces
  // clés restent à zéro et on retombe sur le message initial.
  const fanoutProgress = heatsScrapingTotal > 0 && heatIndex > 0;
  const heatPct = fanoutProgress ? Math.round((heatIndex / heatsScrapingTotal) * 100) : 0;
  // Phase C Klikego (#583) : avancement des participants au sein de la série
  // en cours. Absent tant que le premier lot n'est pas rapporté (`detailTotal`
  // reste à 0 hors Klikego, ou avant la première notification).
  const detailProgress = detailTotal > 0;
  return (
    <div style={{ padding: "14px 18px", background: "var(--tcn-fill)", border: "1px solid var(--tcn-border)", borderRadius: "var(--tcn-radius-xl)" }}>
      {phase === "scraping" ? (
        fanoutProgress ? (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--tcn-text-body)", marginBottom: 8 }}>
              <span style={{ fontWeight: 600 }}>Récupération… série {heatIndex}/{heatsScrapingTotal}</span>
              <span style={{ color: "var(--tcn-text-muted)" }}>{heatLabel}</span>
            </div>
            <div style={{ height: 8, background: "var(--tcn-surface)", borderRadius: 999, overflow: "hidden" }}>
              <div style={{ width: heatPct + "%", height: "100%", background: "var(--tcn-orange)", transition: "width var(--tcn-dur)" }} />
            </div>
            {/* Phase C Klikego (#583) : sans elle, la barre ci-dessus (une
                seule marche par série) reste figée jusqu'à 4 min sur un gros
                heat — l'opérateur n'a aucun signe de vie entre deux séries. */}
            {detailProgress && (
              <div style={{ fontSize: 12, color: "var(--tcn-text-muted)", marginTop: 4, textAlign: "right" }}>
                {detailDone}/{detailTotal} participants
              </div>
            )}
          </>
        ) : (
          <>
            <div style={{ fontSize: 14, color: "var(--tcn-text-body)", fontWeight: 600, marginBottom: 8 }}>
              {message || "Récupération des participants…"}
            </div>
            {/* Barre indéterminée : le scrape n'a aucune progression à rapporter
                avant son premier participant, et une ligne immobile pendant des
                minutes ne se distingue pas d'un écran figé (#491, ACT-4). */}
            <div style={{ height: 8, background: "var(--tcn-surface)", borderRadius: 999, overflow: "hidden" }}>
              <div className="tcn-barre-indeterminee" style={{ height: "100%", width: "35%", background: "var(--tcn-orange)", borderRadius: 999 }} />
            </div>
          </>
        )
      ) : (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--tcn-text-body)", marginBottom: 8 }}>
            <span style={{ fontWeight: 600 }}>Import en cours… {progress}/{total}</span>
            <span style={{ color: "var(--tcn-text-muted)" }}>{imported} ajoutés · {skipped} déjà présents</span>
          </div>
          <div style={{ height: 8, background: "var(--tcn-surface)", borderRadius: 999, overflow: "hidden" }}>
            <div style={{ width: pct + "%", height: "100%", background: "var(--tcn-orange)", transition: "width var(--tcn-dur)" }} />
          </div>
        </>
      )}
      {phase === "scraping" && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginTop: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>
            Import en cours depuis {formatDuree(secondes)}
          </span>
          <Button variant="secondary" size="sm" onClick={onAnnuler}>
            Annuler l&apos;import
          </Button>
        </div>
      )}
    </div>
  );
}
