"use client";

import { useState, type ReactNode } from "react";
import { Tabs } from "@/components/ui/tabs";

// Contrôlé plutôt que remonté par `key` : changer de sexe garde l'onglet ouvert.
// Seul « composition » disparaît sous un filtre et retombe sur « type ».
export function BreakdownTabs({ hasComposition, children }: { hasComposition: boolean; children: ReactNode }) {
  const [tab, setTab] = useState<string>("type");
  if (tab === "composition" && !hasComposition) setTab("type");
  return (
    <Tabs value={tab} onValueChange={(value) => setTab(String(value))}>
      {children}
    </Tabs>
  );
}
