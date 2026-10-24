"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Fragment, useEffect, useRef, useState, type CSSProperties } from "react";
import { Briefcase, Ellipsis, LogIn, Menu, PanelLeft, Plus, RotateCw, Search, X } from "lucide-react";
import { Button } from "@/components/tcn";
import { SessionEnLecture, UserMenu } from "@/components/auth/UserMenu";
import { Sheet, SheetClose, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useSession } from "@/lib/queries/auth";
import { libelleCompteur, totalATraiter, useNavBadges } from "@/lib/queries/nav-badges";
import { SpaceSwitcher, type SwitcherSpace } from "./SpaceSwitcher";
import { AthletePicker, OPEN_PICKER_EVENT, writeAthlete, type PickerMode } from "./AthletePicker";
import { NAV, ROLE, SPACES, byGroup, estVisible, spaceOf, type NavItem, type NavSection, type SpaceId } from "./nav.config";
import { CLUB_NAME, CLUB_NAME_SHORT } from "@/lib/club";
import { NAV_WIDTH_COOKIE } from "@/lib/nav-cookies";

/**
 * Navigation de l'application — rail compact ↔ panneau déplié (proto
 * « Navigation TCN », issue #213).
 *
 * Un seul composant rend les trois formats (rail, panneau, tiroir mobile)
 * depuis `nav.config.ts` : l'arborescence n'est décrite qu'une fois.
 *
 * Deux invariants tenus par le design :
 * - **les deux actions primaires** (« Ajouter une épreuve », « Rechercher un
 *   athlète ») gardent le même ancrage, sous le logo, dans les trois formats ;
 *   la liste des catégories scrolle, ce bloc ne cède jamais (`flex:none`) ;
 * - **les entrées sans écran livré** (`soon`) restent déclarées dans
 *   `nav.config.ts` — c'est la feuille de route — mais ne sont pas rendues
 *   (#242) : la nav n'annonce que ce qui existe.
 */

/** Entrée rendue : une destination livrée, donc porteuse d'un `href`. */
type Destination = NavItem & { href: string; count?: number };
type SectionRendue = Omit<NavSection, "items"> & { items: Destination[] };

export function AppNav({ initialExpanded = false }: { initialExpanded?: boolean }) {
  const pathname = usePathname();
  // Sur `/acces`, l'accès au site n'est pas établi : toute recherche y
  // finirait en 401 (#953).
  const rechercheDisponible = pathname !== "/acces";
  const router = useRouter();
  const { data: session, errorUpdateCount: echecsSession, isFetching: sessionEnCours, refetch: relireSession } = useSession();
  const [drawerOpen, setDrawerOpen] = useState(false);
  // Deux usages, deux modes (#952) : la recherche ne fait que naviguer ; seule
  // la désignation demandée par `OPEN_PICKER_EVENT` retient l'athlète.
  const [pickerMode, setPickerMode] = useState<PickerMode | null>(null);
  // `expanded` vient désormais du cookie lu par `app/layout.tsx` (#482,
  // NAV-3), synchrone dès le premier rendu — plus rien à y lire au montage.
  // Le raccourci clavier reste client-only : `navigator` n'existe pas au rendu
  // serveur.
  const [{ expanded, kbd }, setClient] = useState({
    expanded: initialExpanded,
    kbd: "Ctrl K",
  });

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setClient((c) => ({ ...c, kbd: /Mac|iPhone|iPad/i.test(navigator.userAgent) ? "⌘K" : "Ctrl K" }));
  }, []);

  // ⌘K / Ctrl+K ouvre la recherche athlète depuis n'importe où. Escape est
  // traité par `Modal`.
  useEffect(() => {
    if (!rechercheDisponible) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        // Une palette déjà ouverte garde son mode : la basculer en silence
        // changerait ce qu'écrit le choix en cours (#952).
        setPickerMode((m) => m ?? "search");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rechercheDisponible]);

  // Ouverture de la palette demandée depuis un écran qui n'en porte pas
  // l'état — l'invitation de Mon espace (#502, revue UI/UX item 11).
  // `AppNav` reste l'unique porteur de `pickerMode` ; l'événement ne fait que
  // le lui demander, comme `onOpenPicker` le fait déjà pour le rail et la
  // barre mobile.
  // Un compte rattaché (#1325) ne désigne personne : sa fiche tient lieu de
  // choix, la palette s'ouvre en simple recherche.
  const compteRattache = Boolean(session?.athlete);
  useEffect(() => {
    const onOpen = () => setPickerMode((m) => m ?? (compteRattache ? "search" : "select"));
    window.addEventListener(OPEN_PICKER_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_PICKER_EVENT, onOpen);
  }, [compteRattache]);

  // Le bouton « Réessayer » du rail disparaît avec la panne : sans relais, le
  // focus tomberait sur `body` au retour de la session. Ref de rappel plutôt
  // qu'un effet sur `session` : au premier chargement du menu (#1603), le
  // déclencheur se monte après la session (#1772).
  const relanceRail = useRef(false);
  function relayerFocus(declencheur: HTMLButtonElement | null) {
    if (!declencheur || !relanceRail.current) return;
    relanceRail.current = false;
    if (document.activeElement === document.body) declencheur.focus();
  }
  function relancerSession() {
    if (sessionEnCours) return;
    relanceRail.current = true;
    void relireSession();
  }

  function setExpanded(next: boolean) {
    setClient((c) => ({ ...c, expanded: next }));
    // Cookie plutôt que `localStorage` (#482, NAV-3) : lu par `app/layout.tsx`
    // au prochain chargement, pour peindre la bonne largeur avant la
    // peinture — jamais relayé à l'API, donc sans effet sur le Data Cache
    // (#352). Un an de `max-age` : c'est une préférence d'affichage, pas une
    // session à faire expirer.
    document.cookie = `${NAV_WIDTH_COOKIE}=${next ? "1" : "0"}; path=/; max-age=31536000; SameSite=Lax`;
  }

  // La nav ne distingue qu'anonyme et connecté : c'est le seul échelon que la
  // production attribue aujourd'hui (cf. ROLE dans nav.config.ts). La finesse
  // au-delà vient des **pouvoirs**, seuls réellement renseignés (#115).
  const rank: number = session ? ROLE.CONNECTED : ROLE.ANON;
  const pouvoirs = new Set(session?.permissions ?? []);
  // Encadrement compris : sa file de crédits bénévoles porte une pastille.
  const { counts: badges } = useNavBadges(Boolean(session?.can_administer || session?.can_supervise));
  const toutesSections: SectionRendue[] = NAV.filter((s) => rank >= s.minRole)
    .map((s) => ({
      ...s,
      items: s.items
        .filter((i): i is Destination => estVisible(i, pouvoirs, rank))
        // Le compteur est attaché à la destination plutôt que passé en prop à
        // travers `NavContent` : il suit l'entrée jusqu'aux deux rendus (tuile
        // et ligne dépliée) sans élargir trois signatures au passage.
        .map((i) => (i.badge ? { ...i, count: badges[i.badge] } : i)),
    }))
    // Une section vidée par le filtrage n'a plus qu'un intitulé à afficher —
    // et, sur le rail replié, une tuile qui déplie sur rien. Le cas se produit
    // quand toutes les entrées d'une section sont `soon` (#242) ou hors des
    // pouvoirs de la session — « Club » l'illustrait jusqu'à #487.
    .filter((s) => s.items.length > 0);

  // Le rail et le tiroir ne montrent que l'espace de la page courante ; la
  // palette ⌘K, elle, garde `toutesSections`.
  const espace = spaceOf(pathname);
  const sectionsEspace = toutesSections.filter((s) => s.space === espace);
  // Un espace refusé n'a aucune section visible : la navigation retombe sur
  // l'espace public plutôt que de laisser l'écran de refus sans issue.
  const espaceAffiche: SpaceId = sectionsEspace.length > 0 || (espace === "admin" && session?.can_administer) ? espace : "public";
  const sections = sectionsEspace.length > 0 ? sectionsEspace : toutesSections.filter((s) => s.space === espaceAffiche);

  // Barre basse mobile (#482, NAV-4) : les onglets de l'espace courant,
  // déclarés dans `nav.config.ts` (`bottomBar`). Ceux de l'espace public sont
  // visibles pour tous, donc identiques avant et après la session (#1300).
  // Le back-office ouvre sur son sommaire, qui porte le total « À traiter ».
  // `/admin` existe pour tout compte qui administre, même sans entrée visible.
  const countAdmin = totalATraiter(toutesSections.flatMap((s) => s.items));
  const ongletsEspace = sections.flatMap((s) => s.items).filter((i) => i.bottomBar);
  const barreItems: Destination[] =
    espaceAffiche === "admin"
      ? [{ id: "sommaire", label: "Sommaire", href: "/admin", icon: Briefcase, badge: "backoffice", count: countAdmin }, ...ongletsEspace]
      : ongletsEspace;
  const dansLaBarre = new Set(barreItems.map((i) => i.id));

  // Le tiroir porte « le reste » de l'espace courant : tout ce que la barre ne
  // montre pas. Il s'ouvre par « Plus ».
  const sectionsReste = sections
    .map((s) => ({ ...s, items: s.items.filter((i) => !dansLaBarre.has(i.id)) }))
    .filter((s) => s.items.length > 0);

  // Repli sur toutes les sections de l'espace quand il ne reste rien (#621) : la barre
  // basse est masquée pendant que le tiroir est ouvert (le `Sheet` passe
  // par-dessus), donc un visiteur dont la barre porte tout (anonyme, ou
  // adhérent sans pouvoir) se retrouvait sans aucune destination à l'écran une
  // fois le tiroir ouvert par le hamburger ou « Plus ». Seul cas de doublon avec la barre.
  // Espace public : toujours l'arbre complet, la barre étant masquée tiroir ouvert.
  const sectionsRepli = espaceAffiche === "public" || sectionsReste.length === 0 ? sections : sectionsReste;

  const countEncadrement = toutesSections
    .filter((s) => s.space === "encadrement")
    .flatMap((s) => s.items)
    .reduce((somme, i) => somme + (i.count ?? 0), 0);

  const espacesOuverts: SwitcherSpace[] = (Object.keys(SPACES) as SpaceId[])
    .filter((id) => id === "admin" ? Boolean(session?.can_administer) : toutesSections.some((s) => s.space === id))
    .map((id) => ({
      id,
      label: SPACES[id].label,
      href: SPACES[id].home ?? toutesSections.find((s) => s.space === id)!.items[0].href,
      ...(id === "admin" && countAdmin !== undefined ? { count: countAdmin } : {}),
      ...(id === "encadrement" && countEncadrement > 0 ? { count: countEncadrement } : {}),
    }));


  /**
   * Un `href` de la nav désigne **un** écran, pas une famille : c'est pourquoi
   * la comparaison est une égalité et non un préfixe. `startsWith` allumait
   * « Back-office » (`/admin`) en même temps que `/admin/acces`, et
   * l'aurait fait pour les trois écrans à venir, tous sous `/admin/`.
   */
  function isActive(href: string) {
    return pathname === href;
  }

  // « Plus » porte la position quand la page courante vit dans le tiroir : sans
  // lui, aucun onglet ne dirait où l'on est.
  const plusActif = sectionsReste.some((s) => s.items.some((i) => isActive(i.href)));

  const contenu = (deplie: boolean, fermer?: () => void, listeSections: SectionRendue[] = sections) => (
    <NavContent
      expanded={deplie}
      sections={listeSections}
      isActive={isActive}
      kbd={kbd}
      onNavigate={fermer}
      onOpenPicker={
        rechercheDisponible
          ? () => {
              fermer?.();
              setPickerMode((m) => m ?? "search");
            }
          : undefined
      }
      onExpand={() => setExpanded(true)}
    />
  );

  return (
    <>
      {/* ── Rail / panneau — md+ ── */}
      <nav
        aria-label="Navigation principale"
        className="sticky top-0 z-30 hidden h-screen flex-none md:flex md:flex-col"
        style={{
          width: expanded ? "var(--tcn-nav-panel)" : "var(--tcn-nav-rail)",
          background: "var(--tcn-surface)",
          borderRight: "1px solid var(--tcn-border-strong)",
          transition: "width .22s ease",
        }}
      >
        <div
          style={{
            flex: "none",
            display: "flex",
            flexDirection: expanded ? "row" : "column",
            alignItems: "center",
            justifyContent: expanded ? "flex-start" : "center",
            gap: expanded ? 10 : 4,
            minHeight: 68,
            padding: expanded ? "0 14px" : "8px 0",
            borderBottom: "1px solid var(--tcn-border-faint)",
          }}
        >
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-label={expanded ? "Replier la navigation" : "Déplier la navigation"}
            style={boutonFantome}
          >
            {expanded ? <PanelLeft size={20} /> : <Menu size={20} />}
          </button>
          {expanded ? (
            /* prefetch={false} (#428) : rendu au seul état déplié, ce lien
               monte un second observateur vers `/` alors que l'entrée
               « Accueil » du rail prefetche déjà la route. */
            <Link
              href="/"
              prefetch={false}
              aria-label={`${CLUB_NAME_SHORT} — Accueil`}
              style={{ display: "inline-flex" }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-tcn.png" alt={CLUB_NAME} style={{ height: 26, display: "block" }} />
            </Link>
          ) : (
            // Monogramme du rail replié (#482, NAV-2) : jusqu'ici seule la
            // barre mobile portait une marque dans le HTML servi. Texte plutôt
            // qu'un second asset graphique — `logo-tcn.png` est un wordmark
            // en largeur (rapport 3,1:1), illisible à 76 px de large, et calquer un mark carré
            // dessus aurait rouvert l'identité visuelle (#325), hors mandat de
            // ce lot. Même `aria-label` et même destination que le logo
            // déplié : un seul lien « accueil », deux habillages.
            <Link
              href="/"
              prefetch={false}
              aria-label={`${CLUB_NAME_SHORT} — Accueil`}
              style={{
                display: "inline-flex",
                fontFamily: "var(--tcn-font-display)",
                fontSize: 15,
                letterSpacing: "0.02em",
                color: "var(--tcn-ink)",
                textDecoration: "none",
              }}
            >
              {CLUB_NAME_SHORT}
            </Link>
          )}
          {!expanded && <SpaceSwitcher current={espaceAffiche} spaces={espacesOuverts} layout="column" />}
        </div>
        {expanded && (
          <div style={{ flex: "none", display: "flex", padding: "8px 14px 0" }}>
            <SpaceSwitcher current={espaceAffiche} spaces={espacesOuverts} layout="row" />
          </div>
        )}

        {contenu(expanded)}

        <div style={{ flex: "none", padding: "12px 14px", borderTop: "1px solid var(--tcn-border-faint)" }}>
          {session ? (
            <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: expanded ? "flex-start" : "center" }}>
              <UserMenu triggerRef={relayerFocus} />
              {expanded && (
                <div style={{ flex: 1, minWidth: 0, fontSize: 13, fontWeight: 700, color: "var(--tcn-ink)", ...tronque }}>
                  {session.display_name || session.email}
                </div>
              )}
            </div>
          ) : session === undefined && echecsSession > 0 ? (
            // Une session illisible n'est pas une session anonyme (#954).
            <div
              role="status"
              style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", justifyContent: expanded ? "flex-start" : "center" }}
            >
              {expanded ? (
                <>
                  <span style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>Session indisponible</span>
                  {/* `aria-disabled` plutôt que `disabled`, qui renverrait le focus sur `body` pendant l'essai. */}
                  <Button variant="secondary" size="sm" aria-disabled={sessionEnCours || undefined} onClick={relancerSession}>
                    {sessionEnCours ? "Nouvelle tentative…" : "Réessayer"}
                  </Button>
                </>
              ) : (
                <Tooltip>
                  <TooltipTrigger
                    render={
                      <button
                        type="button"
                        className="tcn-rail-compte"
                        onClick={relancerSession}
                        aria-disabled={sessionEnCours || undefined}
                        aria-label={sessionEnCours ? "Nouvelle tentative…" : "Session indisponible, réessayer"}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: "100%",
                          height: 44,
                          padding: 0,
                          borderRadius: "var(--tcn-radius-lg)",
                          background: "var(--tcn-surface)",
                          color: "var(--tcn-ink)",
                          border: "1.5px solid var(--tcn-border-strong)",
                          cursor: sessionEnCours ? "wait" : "pointer",
                        }}
                      />
                    }
                  >
                    <RotateCw size={18} style={{ flex: "none" }} />
                  </TooltipTrigger>
                  <TooltipContent>{sessionEnCours ? "Nouvelle tentative…" : "Session indisponible, réessayer"}</TooltipContent>
                </Tooltip>
              )}
            </div>
          ) : session === undefined ? (
            // Session encore en lecture : « Se connecter » y mentirait à un
            // connecté pendant toute la durée des essais.
            <div style={{ display: "flex", justifyContent: expanded ? "flex-start" : "center" }}>
              <SessionEnLecture />
            </div>
          ) : (
            <Tooltip>
              <TooltipTrigger
                disabled={expanded}
                render={
                  <button
                    type="button"
                    className="tcn-rail-compte"
                    onClick={() => router.push("/login")}
                    aria-label="Se connecter"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      width: "100%",
                      height: 44,
                      padding: expanded ? "0 14px" : 0,
                      justifyContent: expanded ? "flex-start" : "center",
                      borderRadius: "var(--tcn-radius-lg)",
                      background: "var(--tcn-surface)",
                      color: "var(--tcn-ink)",
                      border: "1.5px solid var(--tcn-border-strong)",
                      fontFamily: "var(--tcn-font-body)",
                      fontWeight: 700,
                      fontSize: 13.5,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      cursor: "pointer",
                    }}
                  />
                }
              >
                <LogIn size={18} style={{ flex: "none" }} />
                {expanded && <span>Se connecter</span>}
              </TooltipTrigger>
              {!expanded && <TooltipContent>Se connecter</TooltipContent>}
            </Tooltip>
          )}
        </div>
      </nav>

      {/* ── Barre mobile — sous md, pas de rail ── */}
      <header
        className="sticky top-0 z-30 flex items-center gap-2 md:hidden"
        style={{
          padding: "8px 12px",
          background: "var(--tcn-surface)",
          borderBottom: "1px solid var(--tcn-border-strong)",
        }}
      >
        {/* État posé à la main : le `Sheet` vit plus bas, hors de portée d'un
            `SheetTrigger` (#1077). */}
        <button
          type="button"
          aria-label="Ouvrir le menu"
          aria-haspopup="dialog"
          aria-expanded={drawerOpen}
          aria-controls={drawerOpen ? TIROIR_ID : undefined}
          onClick={() => setDrawerOpen(true)}
          style={boutonFantome}
        >
          <Menu size={21} />
        </button>
        <Link href="/" aria-label={`${CLUB_NAME_SHORT} — Accueil`} style={{ display: "inline-flex", marginRight: "auto" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-tcn.png" alt={CLUB_NAME} style={{ height: 24, display: "block" }} />
        </Link>
        {rechercheDisponible && (
          <button type="button" aria-label="Rechercher un athlète" onClick={() => setPickerMode((m) => m ?? "search")} style={carreSecondaire}>
            <Search size={18} />
          </button>
        )}
        <Link href="/ajouter" aria-label="Ajouter une épreuve" style={carrePrimaire}>
          <Plus size={20} />
        </Link>
      </header>

      {/* ── Barre basse mobile — les onglets de l'espace courant (#482, NAV-4) ── */}
      <nav
        aria-label="Navigation"
        className="fixed inset-x-0 bottom-0 z-30 flex md:hidden"
        style={{
          height: "var(--tcn-nav-bottom)",
          background: "var(--tcn-surface)",
          borderTop: "1px solid var(--tcn-border-strong)",
        }}
      >
        {barreItems.map((it) => {
          const Icon = it.icon;
          const actif = isActive(it.href);
          return (
            <Link
              key={it.id}
              href={it.href}
              aria-current={actif ? "page" : undefined}
              aria-label={nomAccessibleOnglet(it)}
              style={ongletBarre(actif)}
            >
              {actif && <span data-trait-actif style={traitOnglet} />}
              {Icon && <Icon size={20} />}
              <span>{it.labelCourt ?? it.label}</span>
              {!!it.count && it.badge && (
                <PastilleOnglet count={it.count} annonce={it.labelCourt ? undefined : libelleCompteur(it.badge, it.count)} />
              )}
            </Link>
          );
        })}
        <button
          type="button"
          aria-haspopup="dialog"
          aria-expanded={drawerOpen}
          aria-controls={drawerOpen ? TIROIR_ID : undefined}
          onClick={() => setDrawerOpen(true)}
          style={ongletBarre(plusActif)}
        >
          {plusActif && <span data-trait-actif style={traitOnglet} />}
          <Ellipsis size={20} />
          <span>Plus</span>
        </button>
      </nav>

      {/* ── Tiroir mobile : le panneau déplié, à l'identique ── */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent id={TIROIR_ID} side="left" className="gap-0 p-0">
          <div
            style={{
              flex: "none",
              display: "flex",
              alignItems: "center",
              height: 56,
              padding: "0 14px",
              borderBottom: "1px solid var(--tcn-border-faint)",
            }}
          >
            <SheetTitle style={{ fontSize: 0 }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-tcn.png" alt={`Navigation — ${CLUB_NAME}`} style={{ height: 22, display: "block" }} />
            </SheetTitle>
            {/* Seul contrôle de fermeture exposé à un lecteur d'écran : le voile
                ne l'est pas, et Échap manque sur téléphone (#1116). */}
            <SheetClose aria-label="Fermer le menu" className="tcn-icon-btn" style={{ ...carre, marginLeft: "auto" }}>
              <X size={20} />
            </SheetClose>
          </div>

          {/* Même place que dans le panneau déplié, libellés compris : l'en-tête
              mobile n'a ni la largeur ni le survol qu'il leur faudrait. */}
          {espacesOuverts.length > 1 && (
            <div style={{ flex: "none", display: "flex", padding: "8px 14px 0" }}>
              <SpaceSwitcher current={espaceAffiche} spaces={espacesOuverts} layout="row" />
            </div>
          )}

          {contenu(true, () => setDrawerOpen(false), sectionsRepli)}

          {/* `pleineLargeur` : dans un tiroir, l'état connecté se déplie à plat —
              un menu déroulant y sortirait du piège de focus. */}
          <div style={{ flex: "none", padding: 14, borderTop: "1px solid var(--tcn-border-faint)" }}>
            <UserMenu pleineLargeur onNavigate={() => setDrawerOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      {pickerMode && (
        <AthletePicker
          mode={pickerMode}
          screens={toutesSections
            .flatMap((sec) =>
              sec.items.map((i) => ({
                label: i.label,
                href: i.href,
                context: i.group ? `${sec.label} · ${i.group}` : sec.label,
              })),
            )
            // Hors de la table de nav (#865), mais à portée de la palette : le
            // sommaire et le guide, sous la même garde que leur layout.
            .concat(
              session?.can_administer
                ? [
                    { label: "Back-office", href: "/admin", context: "Administration · Sommaire" },
                    { label: "Guide d'administration", href: "/admin/guide", context: "Administration" },
                  ]
                : [],
            )}
          onClose={() => setPickerMode(null)}
          onPick={(a) => {
            if (pickerMode === "select") writeAthlete(a);
            setPickerMode(null);
            router.push(`/athletes/${a.id}`);
          }}
        />
      )}
    </>
  );
}

/** Actions primaires + catégories — le corps commun aux trois formats. */
function NavContent({
  expanded,
  sections,
  isActive,
  kbd,
  onOpenPicker,
  onNavigate,
  onExpand,
}: {
  expanded: boolean;
  sections: SectionRendue[];
  isActive: (href: string) => boolean;
  kbd: string;
  /** Absent là où la recherche ne peut qu'échouer (`/acces`, #953). */
  onOpenPicker?: () => void;
  onNavigate?: () => void;
  onExpand: () => void;
}) {
  const justify = expanded ? "flex-start" : "center";
  const padAction = expanded ? "0 14px" : "0";

  return (
    <>
      {/* Ancrage fixe des deux actions primaires : elles ne scrollent jamais. */}
      <div
        style={{
          flex: "none",
          display: "flex",
          flexDirection: "column",
          gap: 10,
          padding: "14px 14px 16px",
          borderBottom: "1px solid var(--tcn-border-faint)",
        }}
      >
        {expanded && <div style={eyebrow}>Actions</div>}

        <Tooltip>
          <TooltipTrigger
            disabled={expanded}
            render={
              <Link
                href="/ajouter"
                onClick={onNavigate}
                aria-label="Ajouter une épreuve"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  height: 44,
                  padding: padAction,
                  justifyContent: justify,
                  borderRadius: "var(--tcn-radius-lg)",
                  // 14 px en 800 : aucune taille de ce bouton n'atteint le seuil
                  // « texte large », donc le blanc y demande 4,5:1 — d'où le fond
                  // `-deep`, où il tient 4,57:1 contre 3,68:1 sur l'orange nu (#299).
                  background: "var(--tcn-orange-deep)",
                  color: "#fff",
                  textDecoration: "none",
                  boxShadow: "var(--tcn-shadow-orange)",
                  fontWeight: 800,
                  fontSize: 14,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                }}
              />
            }
          >
            <Plus size={20} style={{ flex: "none" }} />
            {expanded && <span>Ajouter une épreuve</span>}
          </TooltipTrigger>
          {!expanded && <TooltipContent>Ajouter une épreuve</TooltipContent>}
        </Tooltip>

        {onOpenPicker && (
          <Tooltip>
            <TooltipTrigger
              disabled={expanded}
              render={
                <button
                  type="button"
                  onClick={onOpenPicker}
                  aria-label="Rechercher un athlète"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    height: 44,
                    padding: padAction,
                    justifyContent: justify,
                    borderRadius: "var(--tcn-radius-lg)",
                    background: "var(--tcn-surface)",
                    color: "var(--tcn-ink)",
                    border: "1.5px solid var(--tcn-ink)",
                    fontFamily: "var(--tcn-font-body)",
                    fontWeight: 700,
                    fontSize: 14,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    cursor: "pointer",
                  }}
                />
              }
            >
              <Search size={18} style={{ flex: "none" }} />
              {expanded && (
                <>
                  <span style={{ flex: 1, textAlign: "left" }}>Rechercher un athlète</span>
                  <span
                    style={{
                      flex: "none",
                      padding: "2px 7px",
                      borderRadius: "var(--tcn-radius-sm)",
                      background: "var(--tcn-fill)",
                      border: "1px solid var(--tcn-border)",
                      fontFamily: "var(--tcn-font-cond)",
                      fontWeight: 700,
                      fontSize: 11,
                      color: "var(--tcn-text-muted)",
                    }}
                  >
                    {kbd}
                  </span>
                </>
              )}
            </TooltipTrigger>
            {!expanded && <TooltipContent>{`Rechercher un athlète (${kbd})`}</TooltipContent>}
          </Tooltip>
        )}
      </div>

      {/* Catégories — seule zone qui scrolle. */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          padding: "14px 14px 8px",
          display: "flex",
          flexDirection: "column",
          gap: expanded ? 18 : 8,
        }}
      >
        {sections.map((sec) => {
          const actifIci = sec.items.some((i) => isActive(i.href));
          return (
            <div key={sec.id} style={{ position: "relative" }}>
              {expanded && !sec.root && <div style={{ ...eyebrow, paddingBottom: 8 }}>{sec.label}</div>}

              {/* Repliée, une catégorie n'offre qu'une tuile qui déplie. La
                  section racine, elle, garde ses destinations à plat dans les
                  deux états — **au même emplacement de l'arbre** (#428) : un
                  conteneur propre à chaque état remonterait les `Link` à la
                  bascule, malgré une `Entree` unifiée. */}
              {!expanded && !sec.root && sec.items.length > 1 ? (
                <Tooltip>
                  <TooltipTrigger
                    render={<button type="button" onClick={onExpand} aria-label={sec.label} style={tuile(actifIci)} />}
                  >
                    <sec.icon size={20} />
                    {actifIci && <span style={barreActive(9)} />}
                  </TooltipTrigger>
                  <TooltipContent>{sec.label}</TooltipContent>
                </Tooltip>
              ) : (
                // `gap: 0` replié, l'espacement des tuiles venant de leur propre
                // `margin: 0 auto 4px` (cf. `tuile()`) — un `gap` s'y ajouterait.
                // Une section réduite à une seule destination livrée (« Club »
                // aujourd'hui) rend directement son `Entree` ici plutôt que le
                // bouton dépliant ci-dessus : deux gestes pour une seule
                // destination n'ont plus de sens (#482, NAV-2).
                <div style={{ display: "flex", flexDirection: "column", gap: expanded ? 2 : 0 }}>
                  {byGroup(sec.items).map(({ group, items }) => {
                    const entries = items.map((it) => (
                      <Entree key={it.id} item={it} actif={isActive(it.href)} expanded={expanded} onNavigate={onNavigate} />
                    ));
                    // Sous-section (#1246) : un groupe nommé pour le lecteur
                    // d'écran dans les deux états, pour que ses liens restent à
                    // la même place de l'arbre (#428). L'intertitre visible, au
                    // rail déplié seul, double ce nom : il est tu.
                    return group ? (
                      <div
                        key={group}
                        role="group"
                        aria-label={group}
                        style={{ display: "flex", flexDirection: "column", gap: expanded ? 2 : 0 }}
                      >
                        {expanded && (
                          <div aria-hidden="true" style={subheading}>
                            {group}
                          </div>
                        )}
                        {entries}
                      </div>
                    ) : (
                      <Fragment key={items[0].id}>{entries}</Fragment>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

/**
 * Une destination livrée, donc toujours un lien — et **le même** lien dans les
 * deux états du rail (#428) : replié il se réduit à son icône, avec le libellé
 * en infobulle native ; déplié il porte pastille et libellé. Seuls le style et
 * les enfants changent.
 *
 * C'est l'objet du correctif : deux composants distincts (`Tuile` replié,
 * `Entree` déplié) faisaient basculer React entre deux branches JSX
 * structurellement différentes. Le `Link` était démonté puis remonté pour la
 * **même** route, déjà dans le viewport, et son `IntersectionObserver` neuf
 * retirait un second prefetch RSC — mesuré 2 fois à l'atterrissage rail
 * persisté déplié, 3 fois après un pliage/dépliage à la main.
 */

function Entree({
  item,
  actif,
  expanded,
  onNavigate,
}: {
  item: Destination;
  actif: boolean;
  expanded: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  // Replié, le seul porteur visible du libellé était le `title` natif du
  // navigateur — jamais lu au tactile, jamais au clavier (#482, NAV-2). Une
  // infobulle maison le remplace ; `aria-label` reste le nom accessible, donc
  // rien ne change pour les technologies d'assistance. `disabled` plutôt
  // qu'un rendu conditionnel du `Tooltip` lui-même : la structure de l'arbre
  // ne dépend jamais d'`expanded`, seul ce qui protège le montage unique du
  // `Link` (#428).
  return (
    <Tooltip>
      <TooltipTrigger
        disabled={expanded}
        render={
          <Link
            href={item.href}
            onClick={onNavigate}
            aria-label={expanded ? undefined : item.label}
            aria-current={actif ? "page" : undefined}
            style={expanded ? entree(actif) : tuile(actif)}
          />
        }
      >
        {actif && <span style={barreActive(expanded ? 10 : 9)} />}
        {expanded ? (
          <>
            <span
              style={{
                flex: "none",
                width: 5,
                height: 5,
                borderRadius: "var(--tcn-radius-pill)",
                background: actif ? "var(--tcn-orange)" : "var(--tcn-text-disabled)",
              }}
            />
            <span style={{ flex: 1 }}>{item.label}</span>
            {!!item.count && (
              // ARIA 1.2 interdit de nommer un élément de rôle `generic` (un
              // `<span>` nu) : l'`aria-label` posé directement dessus n'a jamais
              // été garanti, il ne « marchait » que par raccroc via le calcul de
              // nom du `<a>` parent. La forme durable : la pastille visuelle
              // passe `aria-hidden`, et un `<span className="sr-only">` porte
              // seul le nom accessible.
              <span style={{ flex: "none", display: "inline-flex", alignItems: "center" }}>
                <span
                  aria-hidden="true"
                  style={{
                    minWidth: 20,
                    padding: "1px 6px",
                    borderRadius: "var(--tcn-radius-pill)",
                    // 11 px / 700 n'atteint aucun seuil de « texte large » : le blanc y
                    // demande 4,5:1, comme sur les boutons primaires du fichier
                    // (l.371, l.705). `--tcn-orange` nu ne tenait que 3,68:1 (#299) ;
                    // `Badge.tsx` porte bien une variante `count`, mais elle compose
                    // `--tcn-orange` sur `--tcn-orange-12` — la même paire que son
                    // propre commentaire chiffre à 2,88:1, donc pas davantage
                    // conforme — et son style (chip translucide) diffère du pastille
                    // pleine attendue ici. On garde le markup, on aligne le token.
                    background: "var(--tcn-orange-deep)",
                    color: "#fff",
                    fontSize: 11,
                    fontWeight: 700,
                    textAlign: "center",
                  }}
                >
                  {item.count}
                </span>
                <span className="sr-only">{libelleCompteur(item.badge, item.count ?? 0)}</span>
              </span>
            )}
          </>
        ) : (
          // Pas de pastille de compteur ici : elle serait inatteignable. Seule
          // la section `root` rend des entrées repliées à plat (l.548), et
          // aucune section à `badge` (« Administration », « Club ») n'est
          // `root`. Porter le signal sur la tuile de catégorie qui la
          // remplace au rail replié est une autre fonctionnalité, hors périmètre
          // (#119).
          Icon && <Icon size={20} />
        )}
      </TooltipTrigger>
      {!expanded && <TooltipContent>{item.label}</TooltipContent>}
    </Tooltip>
  );
}

const TIROIR_ID = "tiroir-navigation";

const tronque = { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } as const;

const eyebrow: CSSProperties = {
  fontFamily: "var(--tcn-font-cond)",
  fontWeight: 700,
  fontSize: 10,
  letterSpacing: "var(--tcn-eyebrow-tracking)",
  textTransform: "uppercase",
  color: "var(--tcn-orange-deeper)",
  padding: "0 2px 2px",
};

const subheading: CSSProperties = {
  fontFamily: "var(--tcn-font-cond)",
  fontWeight: 700,
  fontSize: 12,
  color: "var(--tcn-text-muted)",
  padding: "8px 12px 2px",
};

const boutonFantome: CSSProperties = {
  flex: "none",
  width: 44,
  height: 44,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: "var(--tcn-radius-lg)",
  background: "transparent",
  border: "1px solid transparent",
  color: "var(--tcn-text-muted)",
  cursor: "pointer",
};

const carre: CSSProperties = {
  flex: "none",
  width: 44,
  height: 44,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: "var(--tcn-radius-lg)",
  cursor: "pointer",
};

const carreSecondaire: CSSProperties = {
  ...carre,
  background: "var(--tcn-surface)",
  border: "1.5px solid var(--tcn-ink)",
  color: "var(--tcn-ink)",
};

const carrePrimaire: CSSProperties = {
  ...carre,
  // Même fond que les boutons primaires : le glyphe blanc tenait déjà le seuil
  // non-textuel sur l'orange nu (3,68:1 pour 3:1 requis), mais il aurait été le
  // seul orange de l'interface à porter du blanc sous les 4,5:1 (#299).
  background: "var(--tcn-orange-deep)",
  border: "none",
  color: "#fff",
  boxShadow: "var(--tcn-shadow-orange)",
};

/** Marqueur orange collé au bord du rail (le conteneur a 14px de gouttière). */
/**
 * Nom accessible d'un onglet à `labelCourt` (#1012) : il commence par le texte
 * visible (WCAG 2.5.3), sans quoi la commande vocale « Accueil » ne trouve rien.
 * Le libellé complet suffit quand il commence déjà par le court.
 */
function nomAccessibleOnglet(item: Pick<NavItem, "label" | "labelCourt" | "badge"> & { count?: number }): string | undefined {
  const { label, labelCourt, badge, count } = item;
  if (!labelCourt) return undefined;
  const nom = label.toLocaleLowerCase("fr").startsWith(labelCourt.toLocaleLowerCase("fr"))
    ? label
    : `${labelCourt}, ${label.charAt(0).toLocaleLowerCase("fr")}${label.slice(1)}`;
  return count && badge ? `${nom}, ${libelleCompteur(badge, count)}` : nom;
}

/** Trait de l'onglet courant, pendant horizontal de `barreActive` du rail :
 *  la position ne se dit pas par la seule couleur (WCAG 1.4.1). */
const traitOnglet: CSSProperties = {
  position: "absolute",
  top: 0,
  left: "25%",
  right: "25%",
  height: 3,
  borderRadius: "0 0 3px 3px",
  background: "var(--tcn-orange)",
};

/** Pastille de compteur d'un onglet : décorative, le nom accessible est le texte `sr-only`. */
function PastilleOnglet({ count, annonce }: { count: number; annonce?: string }) {
  return (
    <>
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          top: 4,
          left: "calc(50% + 6px)",
          minWidth: 16,
          padding: "0 4px",
          borderRadius: "var(--tcn-radius-pill)",
          background: "var(--tcn-orange-deep)",
          color: "#fff",
          fontSize: 11,
          fontWeight: 700,
          lineHeight: "16px",
          textAlign: "center",
        }}
      >
        {count}
      </span>
      {annonce && <span className="sr-only">{annonce}</span>}
    </>
  );
}

/** Onglet de la barre basse mobile, lien ou bouton « Plus » (#1012). */
function ongletBarre(actif: boolean): CSSProperties {
  return {
    position: "relative",
    flex: 1,
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
    padding: 0,
    border: 0,
    background: "none",
    cursor: "pointer",
    textDecoration: "none",
    whiteSpace: "nowrap",
    fontFamily: "var(--tcn-font-cond)",
    fontWeight: 700,
    fontSize: 11,
    color: actif ? "var(--tcn-orange-deep)" : "var(--tcn-text-muted)", // 4,57:1 sur blanc (#1078)
  };
}

function barreActive(top: number): CSSProperties {
  return {
    position: "absolute",
    left: -14,
    top,
    width: 3,
    height: 26,
    borderRadius: "0 3px 3px 0",
    background: "var(--tcn-orange)",
  };
}

/** Entrée du panneau déplié — pastille, libellé, et la barre active du bord. */
function entree(actif: boolean): CSSProperties {
  return {
    position: "relative",
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "9px 12px",
    minHeight: 44,
    borderRadius: "var(--tcn-radius-md)",
    textDecoration: "none",
    fontSize: 14,
    fontWeight: actif ? 700 : 500,
    // `-deeper` : `-deep` ne tient que 4,14:1 sur le fond teinté (#1078).
    color: actif ? "var(--tcn-orange-deeper)" : "var(--tcn-text-body)",
    background: actif ? "var(--tcn-orange-08)" : "transparent",
  };
}

/** Tuile du rail replié — 44 px, icône centrée, libellé en infobulle. */
function tuile(actif: boolean): CSSProperties {
  return {
    position: "relative",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: 44,
    height: 44,
    margin: "0 auto 4px",
    borderRadius: "var(--tcn-radius-lg)",
    border: "none",
    cursor: "pointer",
    background: actif ? "var(--tcn-orange-10)" : "transparent",
    color: actif ? "var(--tcn-orange)" : "var(--tcn-text-muted)",
  };
}
