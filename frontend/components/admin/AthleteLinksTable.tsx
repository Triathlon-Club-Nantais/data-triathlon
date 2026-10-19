"use client";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { nomComplet } from "@/components/layout/AthletePicker";
import { useAthleteLinks, useDetachAthleteLink } from "@/lib/queries/admin";
import { messageDeRefus } from "@/lib/api/refus";
import type { AthleteLink } from "@/lib/types";

const REFUS = { sujet: "comptes rattachés", action: "valider les rattachements de fiche" };

/**
 * Comptes rattachés à une fiche (#1633). Le rattachement ne vaut adhésion que si
 * la fiche est licenciée au club cette saison : ceux dont la licence ne court
 * plus viennent en tête. « Détacher » sert au départ d'un adhérent.
 */
export function AthleteLinksTable() {
  const { data, isPending, error } = useAthleteLinks();
  const detacher = useDetachAthleteLink();
  const [cible, setCible] = useState<AthleteLink | null>(null);

  if (isPending) return <Skeleton className="h-32 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (data.length === 0) {
    return <EmptyState title="Aucun compte rattaché" description="Une demande validée ci-dessus apparaîtra ici." />;
  }

  const qui = (link: AthleteLink) => link.user.display_name || link.user.email;

  return (
    <>
      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Compte</TableHead>
              <TableHead>Fiche</TableHead>
              <TableHead>Adhésion par la licence</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((link) => (
              <TableRow key={link.user.id}>
                <TableCell>
                  {link.user.display_name && <div className="font-semibold">{link.user.display_name}</div>}
                  <div className="text-sm text-muted-foreground">{link.user.email}</div>
                </TableCell>
                <TableCell>
                  <Link href={`/athletes/${link.athlete.id}`} className="underline underline-offset-2">
                    {nomComplet(link.athlete)}
                  </Link>
                </TableCell>
                <TableCell>{link.licensed_this_season ? "Licencié cette saison" : "Pas de licence cette saison"}</TableCell>
                <TableCell>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      detacher.reset();
                      setCible(link);
                    }}
                    aria-label={`Détacher ${qui(link)} de sa fiche`}
                  >
                    Détacher
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
      <DangerConfirm
        open={cible !== null}
        onOpenChange={(ouvert) => !ouvert && setCible(null)}
        titre="Détacher ce compte de sa fiche ?"
        description={
          cible ? (
            <>
              {qui(cible)} ne sera plus rattaché à la fiche de {nomComplet(cible.athlete)}, qui reste publiée. Il
              perd son espace personnel, et l&apos;adhésion qu&apos;il tenait de sa licence.
            </>
          ) : null
        }
        libelleAction="Détacher"
        avertissement={detacher.error?.message}
        enAttente={detacher.isPending}
        onConfirm={() => {
          if (!cible) return;
          detacher.mutate(cible.user.id, {
            onSuccess: () => {
              toast.success("Compte détaché.");
              setCible(null);
            },
          });
        }}
      />
    </>
  );
}
