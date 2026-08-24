"use client";
import { createContext, useCallback, useContext, useEffect, useId, useState, type ReactNode } from "react";
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

export type DangerConfirmProps = {
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
  /** Question fermée, nommant sa cible : « Retirer « a@b.fr » ? ». */
  titre: string;
  description?: ReactNode;
  /**
   * Ce que l'appelant sait de particulier sur *ce* clic-ci — « Ce rôle est le
   * vôtre ». Distinct de `description`, qui décrit le geste en général.
   */
  avertissement?: ReactNode;
  /**
   * Mot à recopier pour activer l'action. Réservé aux gestes dont la portée est
   * la base entière : l'exiger partout le viderait de son sens.
   */
  motDeConfirmation?: string;
  /** L'action reste inerte — typiquement, le chiffrage d'impact n'est pas arrivé. */
  actionBloquee?: boolean;
  libelleAction?: string;
  enAttente?: boolean;
  onConfirm: () => void | Promise<void>;
  /** Le corps chiffré, quand le geste annonce son ampleur avant d'agir. */
  children?: ReactNode;
};

/**
 * Le seul mécanisme de confirmation des gestes destructifs de l'administration
 * (#499, `ADM-8`).
 *
 * **Le `Dialog` du produit, jamais le `confirm` du navigateur** : ce dernier
 * n'est ni traduisible, ni stylable, ni testable au même titre. Quatre
 * mécanismes coexistaient pour un même verbe ; il n'en reste qu'un.
 *
 * Deux formes d'appel pour un seul rendu — celle-ci, déclarative, pour les
 * gestes qui chiffrent leur impact avant d'agir ; `useDangerConfirm` pour les
 * gestes simples, qui appelaient `window.confirm`.
 *
 * Vit dans `components/admin/` et non dans `ui/` ou `tcn/` : tous ses appelants
 * sont sous `/admin`, ce qui laisse intacte la frontière gelée par #460.
 */
export function DangerConfirm({
  open,
  onOpenChange,
  titre,
  description,
  avertissement,
  motDeConfirmation,
  actionBloquee = false,
  libelleAction = "Supprimer définitivement",
  enAttente = false,
  onConfirm,
  children,
}: DangerConfirmProps) {
  const [saisie, setSaisie] = useState("");
  const champ = useId();

  // La saisie ne survit pas à une fermeture : rouvrir sur un mot déjà tapé
  // rendrait le garde-fou décoratif.
  useEffect(() => {
    if (!open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSaisie("");
    }
  }, [open]);

  const motManquant = motDeConfirmation !== undefined && saisie !== motDeConfirmation;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{titre}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>

        {avertissement && <p className="text-sm text-destructive">{avertissement}</p>}

        {children}

        {motDeConfirmation !== undefined && (
          <label className="block space-y-1 text-sm" htmlFor={champ}>
            Tapez <strong>{motDeConfirmation}</strong> pour activer la confirmation.
            <Input
              id={champ}
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              autoComplete="off"
              spellCheck={false}
            />
          </label>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Renoncer
          </Button>
          <Button
            variant="destructive"
            onClick={() => void onConfirm()}
            disabled={enAttente || actionBloquee || motManquant}
          >
            {libelleAction}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export type DemandeDeConfirmation = {
  titre: string;
  description?: ReactNode;
  avertissement?: ReactNode;
  libelleAction?: string;
};

const DangerConfirmContext = createContext<
  ((demande: DemandeDeConfirmation) => Promise<boolean>) | null
>(null);

/**
 * Le dialog partagé des gestes simples — ceux qui n'ont pas d'impact à chiffrer.
 *
 * Un provider et non un `useState` par tableau : sans lui, chaque tableau
 * porterait l'état d'ouverture **et** la ligne visée, dupliqués autant de fois
 * qu'il y a d'écrans. Monté dans `app/admin/layout.tsx`, pas à la racine : tous
 * les appelants sont sous `/admin`.
 */
export function DangerConfirmProvider({ children }: { children: ReactNode }) {
  const [enCours, setEnCours] = useState<{
    demande: DemandeDeConfirmation;
    resoudre: (verdict: boolean) => void;
  } | null>(null);

  const confirmer = useCallback(
    (demande: DemandeDeConfirmation) =>
      new Promise<boolean>((resoudre) => setEnCours({ demande, resoudre })),
    [],
  );

  function repondre(verdict: boolean) {
    enCours?.resoudre(verdict);
    setEnCours(null);
  }

  return (
    <DangerConfirmContext.Provider value={confirmer}>
      {children}
      {enCours && (
        <DangerConfirm
          open
          onOpenChange={(ouvert) => {
            // Échap et clic hors du dialog passent par ici : les deux valent un
            // renoncement, sans quoi la promesse ne se résoudrait jamais et
            // l'appelant resterait suspendu.
            if (!ouvert) repondre(false);
          }}
          titre={enCours.demande.titre}
          description={enCours.demande.description}
          avertissement={enCours.demande.avertissement}
          libelleAction={enCours.demande.libelleAction}
          onConfirm={() => repondre(true)}
        />
      )}
    </DangerConfirmContext.Provider>
  );
}

/**
 * Remplace `window.confirm` un pour un :
 * `if (!(await confirmer({ titre, description, libelleAction }))) return;`
 */
export function useDangerConfirm() {
  const confirmer = useContext(DangerConfirmContext);
  if (!confirmer) {
    throw new Error("useDangerConfirm exige un DangerConfirmProvider au-dessus de lui.");
  }
  return confirmer;
}
