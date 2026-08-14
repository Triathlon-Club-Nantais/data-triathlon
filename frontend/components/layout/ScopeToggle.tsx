"use client";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTransition } from "react";
import { Users, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { SCOPE_PARAM, SCOPE_CLUB } from "@/lib/scope";
import { CLUB_NAME, CLUB_NAME_SHORT } from "@/lib/club";

/**
 * Contrôle de portée par page : « Tous » ↔ « Membres TCN ».
 * Pilote le paramètre d'URL `?scope=club` (remplace l'ancien toggle global).
 */
export function ScopeToggle() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [pending, startTransition] = useTransition();
  const clubActive = sp.get(SCOPE_PARAM) === SCOPE_CLUB;

  function setScope(club: boolean) {
    const params = new URLSearchParams(sp.toString());
    if (club) params.set(SCOPE_PARAM, SCOPE_CLUB);
    else params.delete(SCOPE_PARAM);
    const qs = params.toString();
    startTransition(() => router.push(`${pathname}${qs ? `?${qs}` : ""}`));
  }

  return (
    <div
      role="group"
      aria-label="Portée"
      data-pending={pending || undefined}
      className="inline-flex items-center rounded-lg border bg-card p-0.5 data-pending:opacity-70"
    >
      <Segment active={!clubActive} onClick={() => setScope(false)}>
        <Globe className="size-3.5" /> Tous
      </Segment>
      <Segment active={clubActive} onClick={() => setScope(true)} title={`Membres ${CLUB_NAME}`}>
        <Users className="size-3.5" /> Membres {CLUB_NAME_SHORT}
      </Segment>
    </div>
  );
}

function Segment({
  active,
  onClick,
  children,
  title,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors",
        active
          ? "bg-primary text-primary-foreground"
          : "text-[var(--tcn-text-faint)] hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
