"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type CSSProperties } from "react";
import { ChevronRight, LogIn, Menu, PanelLeft, Plus, Search } from "lucide-react";
import { Avatar } from "@/components/tcn";
import { UserMenu } from "@/components/auth/UserMenu";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useSession } from "@/lib/queries/auth";
import { AthletePicker, readAthlete, writeAthlete, type PickedAthlete } from "./AthletePicker";
import { NAV, ROLE, type NavItem, type NavSection } from "./nav.config";
import { CLUB_NAME, CLUB_NAME_SHORT } from "@/lib/club";

/**
 * Navigation de l'application — rail compact ↔ panneau déplié (proto
 * « Navigation TCN », issue #213).
 *
 * Un seul composant rend les trois formats (rail, panneau, tiroir mobile)
 * depuis `nav.config.ts` : l'arborescence n'est décrite qu'une fois.
 *
 * Deux invariants tenus par le design :
 * - **les deux actions primaires** (« Ajouter une course », « Rechercher un
 *   athlète ») gardent le même ancrage, sous le logo, dans les trois formats ;
 *   la liste des catégories scrolle, ce bloc ne cède jamais (`flex:none`) ;
 * - **les entrées sans écran** sont portées désactivées (« À VENIR ») plutôt
 *   qu'inventées.
 */

const STORE_NAV = "tcn-nav-expanded";

export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  // Les trois valeurs que seul le client connaît, en un seul état : le rendu
  // serveur part du rail replié, sans athlète, raccourci PC.
  const [{ expanded, athlete, kbd }, setClient] = useState({
    expanded: false,
    athlete: null as PickedAthlete | null,
    kbd: "Ctrl K",
  });

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem(STORE_NAV);
    } catch {
      /* mode privé : on reste sur le rail compact. */
    }
    // `localStorage` et la plateforme n'existent pas au rendu serveur :
    // l'alignement ne peut avoir lieu qu'au montage, en un seul `setState`.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setClient({
      expanded: stored === "1",
      athlete: readAthlete(),
      kbd: /Mac|iPhone|iPad/i.test(navigator.userAgent) ? "⌘K" : "Ctrl K",
    });
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

  function setExpanded(next: boolean) {
    setClient((c) => ({ ...c, expanded: next }));
    try {
      window.localStorage.setItem(STORE_NAV, next ? "1" : "0");
    } catch {
      /* l'état vaut alors pour l'onglet en cours seul. */
    }
  }

  // La nav ne distingue qu'anonyme et connecté : c'est le seul échelon que la
  // production attribue aujourd'hui (cf. ROLE dans nav.config.ts).
  const rank: number = session ? ROLE.CONNECTED : ROLE.ANON;
  const sections = NAV.filter((s) => rank >= s.minRole).map((s) => ({
    ...s,
    items: s.items.filter((i) => rank >= (i.minRole ?? ROLE.ANON)),
  }));

  function isActive(href: string) {
    return href === "/dashboard"
      ? pathname === "/" || pathname.startsWith("/dashboard")
      : pathname.startsWith(href);
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
            alignItems: "center",
            gap: 10,
            height: 68,
            padding: "0 14px",
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
          {expanded && (
            <Link href="/dashboard" aria-label={`${CLUB_NAME_SHORT} — Accueil`} style={{ display: "inline-flex" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-tcn.png" alt={CLUB_NAME} style={{ height: 26, display: "block" }} />
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
            <button
              type="button"
              onClick={() => router.push("/login")}
              title={expanded ? undefined : "Se connecter"}
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
            >
              <LogIn size={18} style={{ flex: "none" }} />
              {expanded && <span>Se connecter</span>}
            </button>
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
        <Link href="/ajouter" aria-label="Ajouter une course" style={carrePrimaire}>
          <Plus size={20} />
        </Link>
      </header>

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
  sections: NavSection[];
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

        <Link
          href="/ajouter"
          onClick={onNavigate}
          title={expanded ? undefined : "Ajouter une course"}
          aria-label="Ajouter une course"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            height: 44,
            padding: padAction,
            justifyContent: justify,
            borderRadius: "var(--tcn-radius-lg)",
            background: "var(--tcn-orange)",
            color: "#fff",
            textDecoration: "none",
            boxShadow: "var(--tcn-shadow-orange)",
            fontWeight: 800,
            fontSize: 14,
            whiteSpace: "nowrap",
            overflow: "hidden",
          }}
        >
          <Plus size={20} style={{ flex: "none" }} />
          {expanded && <span>Ajouter une course</span>}
        </Link>

        {athlete ? (
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
            <Link
              href={`/athletes/${athlete.id}`}
              onClick={onNavigate}
              aria-label={`Mon profil — ${athlete.name}`}
              title={expanded ? undefined : "Mon profil"}
            >
              <Avatar name={athlete.name} size={30} style={{ boxShadow: "var(--tcn-shadow-orange)" }} />
            </Link>
            {expanded && (
              <>
                <Link
                  href={`/athletes/${athlete.id}`}
                  onClick={onNavigate}
                  style={{ flex: 1, minWidth: 0, fontWeight: 700, fontSize: 14, color: "var(--tcn-orange-deep)", textDecoration: "none", ...tronque }}
                >
                  {athlete.name.split(" ")[0]}
                </Link>
                <button
                  type="button"
                  onClick={onOpenPicker}
                  aria-label="Changer d'athlète"
                  style={{ flex: "none", width: 26, height: 26, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "var(--tcn-radius-pill)", background: "transparent", border: "none", color: "var(--tcn-orange)", cursor: "pointer" }}
                >
                  <ChevronRight size={15} />
                </button>
              </>
            )}
          </div>
        ) : (
          <button
            type="button"
            onClick={onOpenPicker}
            title={expanded ? undefined : `Rechercher un athlète (${kbd})`}
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
          </button>
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
          const actifIci = sec.items.some((i) => i.href && isActive(i.href));
          return (
            <div key={sec.id} style={{ position: "relative" }}>
              {expanded && !sec.root && <div style={{ ...eyebrow, paddingBottom: 8 }}>{sec.label}</div>}

              {/* Rail compact : une tuile par destination pour la section
                  racine, une tuile par catégorie sinon — elle déplie. */}
              {!expanded &&
                (sec.root ? (
                  sec.items.map((it) => (
                    <Tuile key={it.id} item={it} actif={!!it.href && isActive(it.href)} onExpand={onExpand} />
                  ))
                ) : (
                  <button type="button" onClick={onExpand} title={sec.label} aria-label={sec.label} style={tuile(actifIci)}>
                    <sec.icon size={20} />
                    {actifIci && <span style={barreActive(9)} />}
                  </button>
                ))}

              {expanded && (
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {sec.items.map((it) => (
                    <Entree key={it.id} item={it} actif={!!it.href && isActive(it.href)} onNavigate={onNavigate} />
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

/** Tuile du rail compact — icône seule, libellé en infobulle native. */
function Tuile({ item, actif, onExpand }: { item: NavItem; actif: boolean; onExpand: () => void }) {
  const Icon = item.icon;
  const corps = (
    <>
      {Icon && <Icon size={20} />}
      {actif && <span style={barreActive(9)} />}
    </>
  );
  // Sans écran livré : la tuile déplie le panneau, où l'entrée s'annonce « À VENIR ».
  if (!item.href) {
    return (
      <button type="button" onClick={onExpand} title={item.label} aria-label={item.label} style={tuile(false)}>
        {corps}
      </button>
    );
  }
  return (
    <Link
      href={item.href}
      title={item.label}
      aria-label={item.label}
      aria-current={actif ? "page" : undefined}
      style={tuile(actif)}
    >
      {corps}
    </Link>
  );
}

/** Entrée du panneau déplié. Sans `href`, elle est portée mais inerte. */
function Entree({ item, actif, onNavigate }: { item: NavItem; actif: boolean; onNavigate?: () => void }) {
  const base: CSSProperties = {
    position: "relative",
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "9px 12px",
    minHeight: 44,
    borderRadius: "var(--tcn-radius-md)",
    textDecoration: "none",
    fontSize: 14,
  };
  const corps = (
    <>
      {actif && <span style={barreActive(10)} />}
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
      {item.soon && (
        <span style={{ flex: "none", fontFamily: "var(--tcn-font-cond)", fontWeight: 700, fontSize: 10, letterSpacing: "0.06em", color: "var(--tcn-text-disabled)" }}>
          À VENIR
        </span>
      )}
    </>
  );

  if (!item.href) {
    return (
      <span aria-disabled="true" style={{ ...base, fontWeight: 500, color: "var(--tcn-text-faint)" }}>
        {corps}
      </span>
    );
  }
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={actif ? "page" : undefined}
      style={{
        ...base,
        fontWeight: actif ? 700 : 500,
        color: actif ? "var(--tcn-orange)" : "var(--tcn-text-body)",
        background: actif ? "var(--tcn-orange-08)" : "transparent",
      }}
    >
      {corps}
    </Link>
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
  background: "var(--tcn-orange)",
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
