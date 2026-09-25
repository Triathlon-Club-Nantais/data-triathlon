"use client";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AjouterNoteJeuneDialog } from "@/components/admin/jeunes/AjouterNoteJeuneDialog";
import { AppelFin } from "@/components/admin/jeunes/AppelFin";
import { NoteSeanceForm } from "@/components/admin/jeunes/NoteSeanceForm";
import {
  useAddTrainingParticipant,
  useTrainingSession,
  useProfiles,
  useSetPresence,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";

const REFUS = { sujet: "l'appel", action: "consulter l'appel" };

/**
 * L'appel de début (#869) — un jeune par carte, deux gestes : présent ou
 * absent. Mobile-first, patron `CalendrierEntrainements.tsx` (cartes, pas de
 * tableau) : c'est l'écran le plus susceptible d'être ouvert depuis un
 * téléphone, au bord d'un bassin ou d'un plateau d'entraînement.
 *
 * Ajouter un jeune non inscrit le pointe présent **au même geste**
 * (`present: true` passé à `useAddTrainingParticipant`, research.md D4) —
 * inscrire puis pointer séparément exposerait le geste de l'encadrant à deux
 * requêtes, sur un réseau mobile incertain.
 *
 * Bascule vers l'appel de fin (US2) via `Tabs` : sa remontée à chaque
 * activation réinitialise `AppelFin`, ce qui **est** le comportement voulu
 * (FR-007, aucun état conservé côté serveur).
 */
export function AppelPresence({ sessionId }: { sessionId: number }) {
  const { data, isLoading, error } = useTrainingSession(sessionId);
  const profils = useProfiles();
  const session = useSession();
  const setPresence = useSetPresence();
  const ajouter = useAddTrainingParticipant();
  const [jeuneNote, setJeuneNote] = useState<{ id: number; nom: string } | null>(null);

  // Confort d'affichage seul : chaque écriture porte sa propre garde côté API.
  const peutEcrire = session.data?.permissions.includes("jeunes:write") ?? false;

  const participants = data?.participants ?? [];
  const profilsParId = new Map((profils.data ?? []).map((profil) => [profil.id, profil]));
  const idsInscrits = new Set(participants.map((participant) => participant.profile_id));
  const ajoutables = (profils.data ?? []).filter((profil) => !idsInscrits.has(profil.id));

  async function pointer(profileId: number, present: boolean) {
    try {
      await setPresence.mutateAsync({ sessionId, profileId, present });
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function ajouterEtPointer(profileId: number) {
    try {
      await ajouter.mutateAsync({ sessionId, profileId, present: true });
      toast.success("Jeune ajouté et pointé présent.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;

  return (
    <>
      <Tabs defaultValue="debut">
        <TabsList className="w-full">
          <TabsTrigger value="debut">Appel de début</TabsTrigger>
          <TabsTrigger value="fin">Appel de fin</TabsTrigger>
        </TabsList>

        <TabsContent value="debut" className="space-y-4 pt-4">
          <NoteSeanceForm
            sessionId={sessionId}
            note={data?.note ?? ""}
            peutEcrire={peutEcrire}
          />

          {peutEcrire && (
            <div className="space-y-1.5">
              <Label htmlFor="appel-ajouter-jeune">Ajouter un jeune</Label>
              {/* `<select>` natif, patron `GroupDetailDialog` : clavier et
                  lecteur d'écran compris, sans état local — la valeur
                  retombe sur le libellé dès que la liste se rafraîchit. */}
              <select
                id="appel-ajouter-jeune"
                className="border-input h-9 w-full rounded-md border bg-transparent px-2 text-sm"
                value=""
                disabled={ajoutables.length === 0}
                onChange={(e) => e.target.value && ajouterEtPointer(Number(e.target.value))}
              >
                <option value="" disabled>
                  Choisir un jeune…
                </option>
                {ajoutables.map((profil) => (
                  <option key={profil.id} value={profil.id}>
                    {profil.first_name} {profil.last_name}
                  </option>
                ))}
              </select>
              {profils.error && (
                <p className="text-[var(--tcn-text-faint)] text-xs">
                  La liste des jeunes n&apos;a pas pu être chargée : ajouter un
                  jeune n&apos;est pas possible pour l&apos;instant.
                </p>
              )}
            </div>
          )}

          {participants.length === 0 ? (
            <EmptyState
              title="Aucun jeune inscrit"
              description="Ajoutez un jeune pour commencer l'appel."
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {participants.map((participant) => {
                const profil = profilsParId.get(participant.profile_id);
                const nom = profil
                  ? `${profil.first_name} ${profil.last_name}`
                  : `Jeune n° ${participant.profile_id}`;
                return (
                  <Card key={participant.profile_id} className="space-y-2 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{nom}</span>
                      {participant.present === true && <Badge>Présent</Badge>}
                      {participant.present === false && (
                        <Badge variant="secondary">Absent</Badge>
                      )}
                    </div>
                    {peutEcrire && (
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant={participant.present === true ? "default" : "outline"}
                          disabled={setPresence.isPending}
                          onClick={() => pointer(participant.profile_id, true)}
                        >
                          Présent
                        </Button>
                        <Button
                          size="sm"
                          variant={participant.present === false ? "default" : "outline"}
                          disabled={setPresence.isPending}
                          onClick={() => pointer(participant.profile_id, false)}
                        >
                          Absent
                        </Button>
                      </div>
                    )}
                    <div className="flex gap-2">
                      {/* Accès profil (FR-010) : jamais gardé par
                          `peutEcrire`, c'est une navigation, pas une
                          écriture — un porteur de `jeunes:read` seul y a
                          droit comme au reste de l'appel. */}
                      <Link
                        href={`/admin/jeunes/${participant.profile_id}`}
                        className={buttonVariants({ variant: "ghost", size: "sm" })}
                      >
                        Voir le profil
                      </Link>
                      {peutEcrire && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setJeuneNote({ id: participant.profile_id, nom })}
                        >
                          Ajouter une note
                        </Button>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="fin" className="pt-4">
          <AppelFin participants={participants} profils={profils.data ?? []} />
        </TabsContent>
      </Tabs>

      {jeuneNote && (
        <AjouterNoteJeuneDialog
          profileId={jeuneNote.id}
          jeuneNom={jeuneNote.nom}
          open
          onOpenChange={(ouvert) => !ouvert && setJeuneNote(null)}
        />
      )}
    </>
  );
}
