"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "./nav-items";

/** Liste de liens de navigation, partagée par la sidebar et le drawer mobile. */
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => {
        const active =
          pathname === item.href || pathname.startsWith(item.href + "/");
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-sidebar-accent text-sidebar-primary"
                : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
            )}
          >
            <span
              className={cn(
                "grid size-7 shrink-0 place-content-center rounded-md transition-colors",
                active
                  ? "bg-sidebar-primary text-sidebar-primary-foreground"
                  : "bg-sidebar-accent/50 text-sidebar-foreground/70 group-hover:text-sidebar-foreground",
              )}
            >
              <Icon className="size-4" />
            </span>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Bloc marque (logo + wordmark) réutilisé dans la sidebar et le drawer. */
export function SidebarBrand({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link
      href="/dashboard"
      onClick={onNavigate}
      className="flex items-center gap-2.5 px-2"
    >
      <span className="grid size-9 place-content-center rounded-[10px] bg-brand text-brand-foreground text-lg font-extrabold">
        T
      </span>
      <span className="flex flex-col leading-none">
        <span className="text-base font-black tracking-[0.12em] text-sidebar-foreground">
          TCN
        </span>
        <span className="micro-label mt-1 text-[9px] text-sidebar-foreground/55">
          Résultats triathlon
        </span>
      </span>
    </Link>
  );
}
