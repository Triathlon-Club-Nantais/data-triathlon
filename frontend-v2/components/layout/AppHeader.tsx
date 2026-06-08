import Link from "next/link";
import { isClubFilterActive } from "@/lib/club-cookie";
import { ThemeToggle } from "./ThemeToggle";
import { ClubFilterToggle } from "./ClubFilterToggle";
import { GlobalSearch } from "./GlobalSearch";

const NAV = [
  { href: "/dashboard", label: "Tableau de bord" },
  { href: "/resultats", label: "Résultats" },
  { href: "/club", label: "Club" },
  { href: "/carte", label: "Carte" },
  { href: "/ajouter", label: "Ajouter" },
  { href: "/admin", label: "Admin" },
];

export async function AppHeader() {
  const clubActive = await isClubFilterActive();
  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        <Link href="/dashboard" className="font-bold">
          TCN Résultats
        </Link>
        <nav className="hidden gap-4 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <GlobalSearch />
          <ClubFilterToggle active={clubActive} />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
