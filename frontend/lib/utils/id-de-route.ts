import { notFound } from "next/navigation";

/**
 * Identifiant numérique d'un segment dynamique, ou `notFound()`.
 *
 * `/athletes/abc` appelait sinon `/athletes/NaN`, que l'API refuse en 422 :
 * depuis que seul un 404 mène à la page introuvable (#923), ce lien mort
 * tombait sur `app/error.tsx`.
 */
export function idDeRoute(brut: string): number {
  const id = Number(brut);
  if (!Number.isSafeInteger(id) || id <= 0) notFound();
  return id;
}
