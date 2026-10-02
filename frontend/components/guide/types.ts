/**
 * Une capture d'écran illustrant une section du guide, en 1418×840.
 * Prise sur le jeu de démo aux noms anonymisés, jamais sur des données
 * réelles : le dépôt est public, ces images aussi (#926). Build de
 * production, pour qu'aucun badge ni overlay de développement n'y figure.
 */
export type GuideCapture = {
  src: string;
  alt: string;
};

/** Le contenu d'une section du guide (une fonctionnalité documentée). */
export type GuideSection = {
  /** Slug utilisé comme ancre (`#club`) — unique dans son fichier de contenu. */
  id: string;
  titre: string;
  /** Instructions concises, une entrée par étape courte. */
  etapes: string[];
  /** Ce que l'utilisateur cherche à accomplir. */
  casUsage: string;
  captures: GuideCapture[];
  /**
   * Destination du rail que la section décrit (#879) : la section se tait
   * quand le rail tait cette destination au visiteur (`destinationVisible`).
   */
  destination?: string;
};
