import { SidebarBrand, SidebarNav } from "./SidebarNav";

/** Barre latérale persistante (desktop ≥ lg). */
export function AppSidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col gap-6 bg-sidebar px-3 py-5 lg:flex">
      <SidebarBrand />
      <div className="px-1">
        <SidebarNav />
      </div>
      <div className="mt-auto px-3">
        <p className="micro-label text-[9px] text-sidebar-foreground/40">
          Triathlon Club Nantais
        </p>
      </div>
    </aside>
  );
}
