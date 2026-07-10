"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { Button, Modal, Input, Avatar } from "@/components/tcn";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { apiClient } from "@/lib/api/client";
import type { AthleteBrief } from "@/lib/types";

// `hidden: true` → onglet temporairement masqué (issues #10, #28). Code et page
// conservés ; réafficher en retirant le drapeau.
const NAV = [
  { href: "/dashboard", label: "Tableau de bord" },
  { href: "/resultats", label: "Résultats" },
  { href: "/club", label: "Club", hidden: true },
  { href: "/carte", label: "Carte", hidden: true },
  { href: "/admin", label: "Admin", hidden: true },
];

export function TcnTopbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const visibleItems = NAV.filter((item) => !item.hidden);

  function isActive(href: string) {
    return href === "/dashboard"
      ? pathname === "/" || pathname.startsWith("/dashboard")
      : pathname.startsWith(href);
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        padding: "14px 16px",
        background: "var(--tcn-surface)",
        borderBottom: "1px solid var(--tcn-border-strong)",
      }}
      className="sm:px-10"
    >
      {/* Logo */}
      <Link href="/dashboard" aria-label="TCN — Accueil" style={{ display: "inline-flex", alignItems: "center", flexShrink: 0 }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo-tcn.png" alt="Triathlon Club Nantais" style={{ height: 34, width: "auto", display: "block" }} />
      </Link>

      {/* Nav desktop (cachée sur mobile) */}
      <div className="hidden sm:flex sm:items-center sm:gap-1">
        <div style={{ width: 1, height: 26, background: "var(--tcn-border-strong)", marginRight: 10 }} />
        <nav style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {visibleItems.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                style={{
                  padding: "7px 12px",
                  borderRadius: "var(--tcn-radius-lg)",
                  fontSize: 14,
                  fontWeight: active ? 700 : 600,
                  color: active ? "var(--tcn-orange)" : "var(--tcn-text-muted)",
                  background: active ? "var(--tcn-orange-10)" : "transparent",
                  textDecoration: "none",
                  whiteSpace: "nowrap",
                }}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Actions desktop (cachées sur mobile) */}
      <div className="hidden sm:flex sm:items-center sm:gap-3">
        <Button
          variant="secondary"
          onClick={() => setPickerOpen(true)}
          icon={
            <span
              style={{
                display: "inline-flex",
                width: 20,
                height: 20,
                borderRadius: 999,
                background: "var(--tcn-orange)",
                color: "#fff",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 11,
                fontWeight: 800,
              }}
            >
              ★
            </span>
          }
        >
          Sélectionner mon nom
        </Button>
        <Button onClick={() => router.push("/ajouter")} icon={<span style={{ fontSize: 18, lineHeight: 1 }}>+</span>}>
          Ajouter un triathlon
        </Button>
      </div>

      {/* Bouton hamburger mobile (caché sur sm+) */}
      <button
        type="button"
        aria-label="Ouvrir le menu"
        onClick={() => setDrawerOpen(true)}
        className="sm:hidden flex items-center justify-center flex-shrink-0"
        style={{
          width: 40,
          height: 40,
          borderRadius: "var(--tcn-radius-lg)",
          background: "var(--tcn-fill)",
          border: "1px solid var(--tcn-border-strong)",
          cursor: "pointer",
        }}
      >
        <Menu size={20} color="var(--tcn-ink)" />
      </button>

      {/* Drawer de navigation mobile */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="left">
          <SheetTitle>Navigation</SheetTitle>
          <nav style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
            {visibleItems.map((item) => {
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setDrawerOpen(false)}
                  style={{
                    padding: "11px 14px",
                    borderRadius: "var(--tcn-radius-lg)",
                    fontSize: 15,
                    fontWeight: active ? 700 : 600,
                    color: active ? "var(--tcn-orange)" : "var(--tcn-text-muted)",
                    background: active ? "var(--tcn-orange-10)" : "transparent",
                    textDecoration: "none",
                  }}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--tcn-border)" }}>
            <Button
              variant="secondary"
              onClick={() => {
                setDrawerOpen(false);
                setPickerOpen(true);
              }}
              style={{ justifyContent: "flex-start" }}
              icon={
                <span style={{ display: "inline-flex", width: 20, height: 20, borderRadius: 999, background: "var(--tcn-orange)", color: "#fff", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800 }}>★</span>
              }
            >
              Sélectionner mon nom
            </Button>
            <Button
              onClick={() => {
                setDrawerOpen(false);
                router.push("/ajouter");
              }}
              icon={<span style={{ fontSize: 18, lineHeight: 1 }}>+</span>}
            >
              Ajouter un triathlon
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {pickerOpen && (
        <AthletePicker
          onClose={() => setPickerOpen(false)}
          onPick={(id) => {
            setPickerOpen(false);
            router.push(`/athletes/${id}`);
          }}
        />
      )}
    </div>
  );
}

type AthleteRow = AthleteBrief & { count: number };

function AthletePicker({ onClose, onPick }: { onClose: () => void; onPick: (id: number) => void }) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<AthleteRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setRows([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const parts = await apiClient.listParticipations({ name: q, page_size: 100 });
        if (cancelled) return;
        const byAthlete = new Map<number, AthleteRow>();
        for (const p of parts) {
          const a = p.athlete;
          const existing = byAthlete.get(a.id);
          if (existing) existing.count += 1;
          else byAthlete.set(a.id, { ...a, count: 1 });
        }
        setRows([...byAthlete.values()].sort((x, y) => y.count - x.count).slice(0, 12));
      } catch {
        if (!cancelled) setRows([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [query]);

  return (
    <Modal
      eyebrow="Accès athlète"
      title="Sélectionne ton nom"
      onClose={onClose}
      width={520}
      footer={
        <div style={{ fontSize: 13, color: "var(--tcn-text-faint)", textAlign: "center" }}>
          Pas de blocage d&apos;accès — choisis librement ton profil.
        </div>
      }
    >
      <Input
        icon={<span>⌕</span>}
        value={query}
        autoFocus
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Rechercher un nom…"
      />
      <div style={{ marginTop: 8 }}>
        {rows.map((a) => {
          const fullName = [a.prenom, a.nom].filter(Boolean).join(" ");
          return (
            <div
              key={a.id}
              role="button"
              tabIndex={0}
              aria-label={`Choisir ${fullName}`}
              onClick={() => onPick(a.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onPick(a.id);
                }
              }}
              style={{ display: "flex", alignItems: "center", gap: 14, padding: "11px 14px", borderRadius: 12, cursor: "pointer" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--tcn-fill)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              onFocus={(e) => (e.currentTarget.style.background = "var(--tcn-fill)")}
              onBlur={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <Avatar name={fullName} size={40} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, color: "var(--tcn-ink)", fontSize: 15 }}>{fullName}</div>
                <div style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>
                  {a.club ?? "Sans club"} · {a.count} course{a.count > 1 ? "s" : ""}
                </div>
              </div>
              <span style={{ color: "var(--tcn-text-disabled)", fontSize: 18 }}>→</span>
            </div>
          );
        })}
        {query.trim().length >= 2 && !loading && rows.length === 0 && (
          <div style={{ padding: 30, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>Aucun athlète trouvé.</div>
        )}
        {query.trim().length < 2 && (
          <div style={{ padding: 30, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>
            Saisis au moins 2 lettres de ton nom.
          </div>
        )}
      </div>
    </Modal>
  );
}
