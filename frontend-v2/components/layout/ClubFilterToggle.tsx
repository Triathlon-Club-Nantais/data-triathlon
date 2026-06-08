"use client";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Users } from "lucide-react";
import { CLUB_COOKIE } from "@/lib/club-constants";

export function ClubFilterToggle({ active }: { active: boolean }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function toggle() {
    const next = active ? "0" : "1";
    document.cookie = `${CLUB_COOKIE}=${next}; path=/; max-age=31536000`;
    startTransition(() => router.refresh());
  }

  return (
    <Button
      variant={active ? "default" : "outline"}
      size="sm"
      onClick={toggle}
      disabled={pending}
    >
      <Users className="mr-2 h-4 w-4" />
      {active ? "Membres TCN" : "Tous"}
    </Button>
  );
}
