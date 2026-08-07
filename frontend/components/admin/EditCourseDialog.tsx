"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EVENT_TYPE_OPTIONS, eventTypeLabel } from "@/lib/constants";
import { useUpdateCourse } from "@/lib/queries/admin";
import type { CourseBrief } from "@/lib/types";

/**
 * Corriger le libellé d'une épreuve (#117, US4).
 *
 * Ces quatre champs **sont** la clé qui distingue deux épreuves l'une de
 * l'autre : une correction mal faite fusionne ou dédouble un pan du catalogue.
 * Le serveur refuse la collision et nomme l'épreuve en cause ; l'écran se
 * contente de restituer ce refus sans vider la saisie.
 */
export function EditCourseDialog({
  course,
  open,
  onOpenChange,
}: {
  course: CourseBrief;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const [nom, setNom] = useState(course.name);
  const [date, setDate] = useState(course.event_date ?? "");
  const [type, setType] = useState(course.event_type);
  const [relais, setRelais] = useState(course.is_relay);
  const correction = useUpdateCourse();

  // Un type absent de la table de libellés (slug d'un scraper en avance sur
  // elle) reste proposé, sous son slug brut : sans cette entrée, ouvrir le
  // dialogue pour corriger la *date* retyperait l'épreuve au passage.
  const inconnu =
    course.event_type && !EVENT_TYPE_OPTIONS.some((o) => o.value === course.event_type);
  const options = inconnu
    ? [{ value: course.event_type, label: course.event_type }, ...EVENT_TYPE_OPTIONS]
    : EVENT_TYPE_OPTIONS;

  async function enregistrer() {
    try {
      await correction.mutateAsync({
        id: course.id,
        champs: {
          name: nom,
          event_date: date === "" ? null : date,
          event_type: type,
          is_relay: relais,
        },
      });
      toast.success("Épreuve corrigée.");
      onOpenChange(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Corriger l&apos;épreuve</DialogTitle>
          <DialogDescription>
            Ces quatre champs distinguent une épreuve d&apos;une autre. Les résultats
            ne sont pas touchés.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="course-nom">Nom</Label>
            <Input id="course-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="course-date">Date</Label>
            <Input
              id="course-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="course-type">Type</Label>
            <Select value={type} onValueChange={(v) => setType(v as string)}>
              <SelectTrigger id="course-type" className="w-full">
                <SelectValue placeholder="Choisir une discipline">
                  {(v) => eventTypeLabel(v as string)}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {options.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <input
              id="course-relais"
              type="checkbox"
              checked={relais}
              onChange={(e) => setRelais(e.target.checked)}
            />
            <Label htmlFor="course-relais">Épreuve en relais</Label>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Renoncer
          </Button>
          <Button onClick={enregistrer} disabled={correction.isPending}>
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
