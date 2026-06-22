"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";

export function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  function submit() {
    const q = value.trim();
    setOpen(false);
    setValue("");
    if (q) router.push(`/resultats?name=${encodeURIComponent(q)}`);
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <Search className="mr-2 h-4 w-4" />
        Rechercher un athlète…
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen} title="Recherche">
        <CommandInput
          placeholder="Nom d'un athlète…"
          value={value}
          onValueChange={setValue}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <CommandList>
          <CommandEmpty>Appuyez sur Entrée pour rechercher.</CommandEmpty>
          <CommandGroup heading="Recherche">
            <CommandItem onSelect={submit}>
              Rechercher « {value} » dans les résultats
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
