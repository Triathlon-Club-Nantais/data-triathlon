"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type CSSProperties } from "react";
import { LogIn, Menu, PanelLeft, Plus, Search, X } from "lucide-react";
import { Avatar } from "@/components/tcn";
import { UserMenu } from "@/components/auth/UserMenu";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useSession } from "@/lib/queries/auth";
import { useNavBadges } from "@/lib/queries/nav-badges";
import { AthletePicker, ATHLETE_CHANGED_EVENT, clearAthlete, nomComplet, readAthlete, writeAthlete, type PickedAthlete } from "./AthletePicker";
import { NAV, ROLE, estVisible, type NavItem, type NavSection } from "./nav.config";
import { CLUB_NAME, CLUB_NAME_SHORT } from "@/lib/club";

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

const STORE_NAV = "tcn-nav-expanded";

export function AppNav({ initialExpanded = false }: { initialExpanded?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  // `expanded` vient désormais du cookie lu par `app/layout.tsx` (#482,
  // NAV-3), synchrone dès le premier rendu — plus rien à y lire au montage.
  // `athlete` et raccourci clavier restent client-only : `localStorage` et
  // `navigator` n'existent pas au rendu serveur.
  const [{ expanded, athlete, kbd }, setClient] = useState({
    expanded: initialExpanded,
    athlete: null as PickedAthlete | null,
    kbd: "Ctrl K",
  });

  useEffect(() => {
    // `localStorage` et `navigator` n'existent pas au rendu serveur : leur
    // lecture ne peut avoir lieu qu'au montage, en un seul `setState`.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setClient((c) => ({
      ...c,
      athlete: readAthlete(),
      kbd: /Mac|iPhone|iPad/i.test(navigator.userAgent) ? "⌘K" : "Ctrl K",
    }));
  }, []);

  // ⌘K / Ctrl+K ouvre la recherche athlète depuis n'importe où. Escape est
  // traité par `Modal`.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPickerOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Se resynchronise sur toute écriture faite ailleurs (bouton de la page
  // profil, #323) — se redéclenche aussi sur les écritures faites par le
  // picker local (l.288-293) : re-lecture idempotente de la même valeur, pas
  // un bug à corriger.
  useEffect(() => {
    const onChange = () => setClient((c) => ({ ...c, athlete: readAthlete() }));
    window.addEventListener(ATHLETE_CHANGED_EVENT, onChange);
    return () => window.removeEventListener(ATHLETE_CHANGED_EVENT, onChange);
  }, []);

  function setExpanded(next: boolean) {
    setClient((c) => ({ ...c, expanded: next }));
    // Cookie plutôt que `localStorage` (#482, NAV-3) : lu par `app/layout.tsx`
    // au prochain chargement, pour peindre la bonne largeur avant la
    // peinture — jamais relayé à l'API, donc sans effet sur le Data Cache
    // (#352). Un an de `max-age` : c'est une préférence d'affichage, pas une
    // session à faire expirer.
    document.cookie = `${STORE_NAV}=${next ? "1" : "0"}; path=/; max-age=31536000; SameSite=Lax`;
  }

  // La nav ne distingue qu'anonyme et connecté : c'est le seul échelon que la
  // production attribue aujourd'hui (cf. ROLE dans nav.config.ts). La finesse
  // au-delà vient des **pouvoirs**, seuls réellement renseignés (#115).
  const rank: number = session ? ROLE.CONNECTED : ROLE.ANON;
  const pouvoirs = new Set(session?.permissions ?? []);
  const badges = useNavBadges(pouvoirs);
  const sections = NAV.filter((s) => rank >= s.minRole)
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
    // et, sur le rail replié, une tuile qui déplie sur rien. C'est le cas de
    // « Club », dont les deux entrées sont à venir (#242).
    .filter((s) => s.items.length > 0);

  // Barre basse mobile (#482, NAV-4) : jamais codé en dur — dérivé des
  // sections dont `minRole` vaut `ROLE.ANON`, pour rester aligné avec
  // `nav.config.ts` au fil des livraisons futures (ex. « Carte », #10/#28).
  const publicItems = sections.filter((s) => s.minRole === ROLE.ANON).flatMap((s) => s.items);

  /**
   * Un `href` de la nav désigne **un** écran, pas une famille : c'est pourquoi
   * la comparaison est une égalité et non un préfixe. `startsWith` allumait
   * « Chronométreurs signalés » (`/admin`) en même temps que `/admin/acces`, et
   * l'aurait fait pour les trois écrans à venir, tous sous `/admin/`.
   *
   * `/dashboard` garde son cas propre : il répond aussi à la racine.
   */
  function isActive(href: string) {
    return pathname === href || (href === "/dashboard" && pathname === "/");
  }

  const contenu = (deplie: boolean, fermer?: () => void) => (
    <NavContent
      expanded={deplie}
      sections={sections}
      isActive={isActive}
      athlete={athlete}
      kbd={kbd}
      onNavigate={fermer}
      onOpenPicker={() => {
        fermer?.();
        setPickerOpen(true);
      }}
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
            justifyContent: "center",
            gap: expanded ? 10 : 4,
            height: 68,
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
               monte un second observateur vers `/dashboard` alors que l'entrée
               « Tableau de bord » du rail prefetche déjà la route. */
            <Link
              href="/dashboard"
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
            // 2000×638, illisible à 76 px de large, et calquer un mark carré
            // dessus aurait rouvert l'identité visuelle (#325), hors mandat de
            // ce lot. Même `aria-label` et même destination que le logo
            // déplié : un seul lien « accueil », deux habillages.
            <Link
              href="/dashboard"
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
        </div>

        {contenu(expanded)}

        <div style={{ flex: "none", padding: "12px 14px", borderTop: "1px solid var(--tcn-border-faint)" }}>
          {session ? (
            <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: expanded ? "flex-start" : "center" }}>
              <UserMenu />
              {expanded && (
                <div style={{ flex: 1, minWidth: 0, fontSize: 13, fontWeight: 700, color: "var(--tcn-ink)", ...tronque }}>
                  {session.display_name || session.email}
                </div>
              )}
            </div>
          ) : (
            <Tooltip>
              <TooltipTrigger
                disabled={expanded}
                render={
                  <button
                    type="button"
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
        <button
          type="button"
          aria-label="Ouvrir le menu"
          onClick={() => setDrawerOpen(true)}
          style={boutonFantome}
        >
          <Menu size={21} />
        </button>
        <Link href="/dashboard" aria-label={`${CLUB_NAME_SHORT} — Accueil`} style={{ display: "inline-flex", marginRight: "auto" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-tcn.png" alt={CLUB_NAME} style={{ height: 24, display: "block" }} />
        </Link>
        <button type="button" aria-label="Rechercher un athlète" onClick={() => setPickerOpen(true)} style={carreSecondaire}>
          <Search size={18} />
        </button>
        <Link href="/ajouter" aria-label="Ajouter une épreuve" style={carrePrimaire}>
          <Plus size={20} />
        </Link>
      </header>

      {/* ── Barre basse mobile — 3 destinations publiques (#482, NAV-4) ── */}
      <nav
        aria-label="Navigation"
        className="fixed inset-x-0 bottom-0 z-30 flex md:hidden"
        style={{
          height: "var(--tcn-nav-bottom)",
          background: "var(--tcn-surface)",
          borderTop: "1px solid var(--tcn-border-strong)",
        }}
      >
        {publicItems.map((it) => {
          const Icon = it.icon;
          const actif = isActive(it.href);
          return (
            <Link
              key={it.id}
              href={it.href}
              aria-current={actif ? "page" : undefined}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 2,
                textDecoration: "none",
                fontFamily: "var(--tcn-font-cond)",
                fontWeight: 700,
                fontSize: 11,
                color: actif ? "var(--tcn-orange)" : "var(--tcn-text-muted)",
              }}
            >
              {Icon && <Icon size={20} />}
              <span>{it.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* ── Tiroir mobile : le panneau déplié, à l'identique ── */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="left" className="gap-0 p-0">
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
          </div>

          {contenu(true, () => setDrawerOpen(false))}

          {/* `pleineLargeur` : dans un tiroir, l'état connecté se déplie à plat —
              un menu déroulant y sortirait du piège de focus. */}
          <div
            style={{ flex: "none", padding: 14, borderTop: "1px solid var(--tcn-border-faint)" }}
            onClick={() => setDrawerOpen(false)}
          >
            <UserMenu pleineLargeur />
          </div>
        </SheetContent>
      </Sheet>

      {pickerOpen && (
        <AthletePicker
          onClose={() => setPickerOpen(false)}
          onPick={(a) => {
            writeAthlete(a);
            setClient((c) => ({ ...c, athlete: a }));
            setPickerOpen(false);
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
  athlete,
  kbd,
  onOpenPicker,
  onNavigate,
  onExpand,
}: {
  expanded: boolean;
  sections: SectionRendue[];
  isActive: (href: string) => boolean;
  athlete: PickedAthlete | null;
  kbd: string;
  onOpenPicker: () => void;
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

        {/* L'entrée recherche reste rendue dans tous les cas — athlète
            retenu ou non — pour ne jamais redevenir inaccessible autrement
            que par le raccourci clavier (issue #323). La tuile de l'athlète
            retenu s'affiche en complément, jamais à sa place. */}
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

        {athlete && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              height: 44,
              padding: expanded ? "0 8px" : 0,
              justifyContent: justify,
              borderRadius: "var(--tcn-radius-lg)",
              background: "var(--tcn-orange-08)",
              border: "1.5px solid var(--tcn-orange-12)",
            }}
          >
            {/* prefetch={false} (#425) : un athlète épinglé au hasard depuis
                le picker, pas une destination probable — inutile de le
                prefetcher dès que la tuile entre dans le viewport. */}
            <Tooltip>
              <TooltipTrigger
                disabled={expanded}
                render={
                  <Link
                    href={`/athletes/${athlete.id}`}
                    prefetch={false}
                    onClick={onNavigate}
                    aria-label={`Mon profil — ${nomComplet(athlete)}`}
                  />
                }
              >
                <Avatar name={nomComplet(athlete)} size={30} style={{ boxShadow: "var(--tcn-shadow-orange)" }} />
              </TooltipTrigger>
              {!expanded && <TooltipContent>Mon profil</TooltipContent>}
            </Tooltip>
            {expanded && (
              <>
                <Link
                  href={`/athletes/${athlete.id}`}
                  prefetch={false}
                  onClick={onNavigate}
                  style={{ flex: 1, minWidth: 0, fontWeight: 700, fontSize: 14, color: "var(--tcn-orange-deep)", textDecoration: "none", ...tronque }}
                >
                  {/* Le prénom vient de l'API, jamais d'un découpage du nom
                      complet : « Jean Gael » est **un** prénom, et
                      `split(" ")[0]` n'en rendait que la moitié (#264). Repli
                      sur le nom, faute de quoi la tuile n'aurait pas de
                      libellé pour un athlète sans prénom renseigné. */}
                  {athlete.prenom || athlete.nom}
                </Link>
                {/* Croix de désélection (#442) — offerte au seul rail déplié :
                    replié, la tuile fait 44 px et l'avatar l'occupe entière.
                    `clearAthlete` émet `ATHLETE_CHANGED_EVENT`, que `AppNav`
                    écoute déjà (l.84) : la tuile disparaît par ce chemin, sans
                    rappel à faire descendre jusqu'ici. Le nom complet, et non
                    le prénom, parce qu'un libellé d'action se lit hors
                    contexte. */}
                <button
                  type="button"
                  onClick={() => clearAthlete()}
                  aria-label={`Ne plus choisir ${nomComplet(athlete)}`}
                  title="Ne plus choisir"
                  className="tcn-icon-btn"
                  style={{
                    flex: "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    // 44 px, le plancher tactile de la grille : la croix est
                    // aussi rendue dans le tiroir mobile, où le rail est
                    // déplié. La hauteur est gratuite, la tuile en fait déjà
                    // autant ; la largeur coûte 16 px à la colonne du prénom,
                    // que `tronque` écourtait déjà.
                    width: 44,
                    height: 44,
                    borderRadius: "var(--tcn-radius-sm)",
                    border: "none",
                    background: "transparent",
                    color: "var(--tcn-orange-deep)",
                    cursor: "pointer",
                  }}
                >
                  <X size={16} />
                </button>
              </>
            )}
          </div>
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
                  {sec.items.map((it) => (
                    <Entree
                      key={it.id}
                      item={it}
                      actif={isActive(it.href)}
                      expanded={expanded}
                      onNavigate={onNavigate}
                    />
                  ))}
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

/**
 * Nom accessible du compteur d'une entrée (#119) : un lecteur d'écran annonçant
 * juste le chiffre (« Revalidation qualité 4 ») ne dit pas ce qu'il dénombre.
 *
 * Une seule clé de badge existe aujourd'hui (`quality`) ; ce switch grandira
 * avec les prochaines, sur le même patron que `useNavBadges`.
 */
function libelleCompteur(item: Destination): string {
  const n = item.count ?? 0;
  switch (item.badge) {
    case "quality":
      return `${n} épreuve${n > 1 ? "s" : ""} à revalider`;
    default:
      return String(n);
  }
}

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
                <span className="sr-only">{libelleCompteur(item)}</span>
              </span>
            )}
          </>
        ) : (
          // Pas de pastille de compteur ici : elle serait inatteignable. Seule
          // la section `root` rend des entrées repliées à plat (l.548), et
          // « Administration » — seule section à porter un `badge` aujourd'hui —
          // n'est pas `root`. Porter le signal sur la tuile de catégorie qui la
          // remplace au rail replié est une autre fonctionnalité, hors périmètre
          // (#119).
          Icon && <Icon size={20} />
        )}
      </TooltipTrigger>
      {!expanded && <TooltipContent>{item.label}</TooltipContent>}
    </Tooltip>
  );
}

const tronque = { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } as const;

const eyebrow: CSSProperties = {
  fontFamily: "var(--tcn-font-cond)",
  fontWeight: 700,
  fontSize: 10,
  letterSpacing: "var(--tcn-eyebrow-tracking)",
  textTransform: "uppercase",
  color: "var(--tcn-text-disabled)",
  padding: "0 2px 2px",
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
    color: actif ? "var(--tcn-orange)" : "var(--tcn-text-body)",
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
