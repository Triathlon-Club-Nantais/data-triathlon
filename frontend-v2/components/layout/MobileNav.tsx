"use client";
import { useState } from "react";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { SidebarBrand, SidebarNav } from "./SidebarNav";

/** Bouton hamburger + drawer de navigation (mobile / tablette < lg). */
export function MobileNav() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <Button variant="ghost" size="icon" aria-label="Ouvrir le menu" />
        }
      >
        <Menu className="size-5" />
      </SheetTrigger>
      <SheetContent side="left">
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <div className="mb-2">
          <SidebarBrand onNavigate={close} />
        </div>
        <SidebarNav onNavigate={close} />
      </SheetContent>
    </Sheet>
  );
}
