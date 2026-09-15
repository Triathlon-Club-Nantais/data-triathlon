/** Une capture d'écran illustrant une section du guide. */
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
};
