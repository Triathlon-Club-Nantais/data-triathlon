import { MobileNav } from "./MobileNav";
import { GlobalSearch } from "./GlobalSearch";
import { ThemeToggle } from "./ThemeToggle";

/** Barre supérieure fine de la zone de contenu (menu mobile + recherche + thème). */
export function Topbar() {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b bg-background/85 px-4 backdrop-blur md:px-6">
      <div className="lg:hidden">
        <MobileNav />
      </div>
      <div className="ml-auto flex items-center gap-2">
        <GlobalSearch />
        <ThemeToggle />
      </div>
    </header>
  );
}
