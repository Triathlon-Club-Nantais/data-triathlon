import { useRoles } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import type { Role } from "@/lib/types";

/**
 * L'inventaire des rôles, et lesquels l'auteur peut réellement donner (#115).
 *
 * Deux écrans posent la même question — attribuer un rôle à quelqu'un, et
 * choisir celui qu'une adresse donnera à l'inscription (#239) — et le service
 * y répond par le même 403. En avoir deux copies les ferait diverger au premier
 * ajustement, dans le sens le plus dangereux : celui qui propose ce qui sera
 * refusé.
 *
 * **Confort d'affichage seul.** La règle est tenue par
 * `authorization.assert_may_hand_over` ; ce qui est ici évite d'annoncer un
 * geste qui rendrait 403, il ne garde rien.
 */
export function useRolesAttribuables() {
  const { data: roles } = useRoles();
  const { data: session } = useSession();

  const pouvoirs = new Set(session?.permissions ?? []);
  // Le rôle superutilisateur ne se distribue qu'entre superutilisateurs
  // (FR-010) : il ne porte souvent **aucun** code, la comparaison ci-dessous le
  // laisserait donc passer. Reconnu par recoupement des deux listes déjà
  // chargées — la session nomme ses rôles, l'inventaire dit lesquels
  // franchissent tout.
  const suisSuperutilisateur = (session?.roles ?? []).some(
    (mien) => roles?.find((role) => role.id === mien.id)?.is_superuser,
  );

  return {
    roles: roles ?? [],
    accordable: (role: Role) =>
      (!role.is_superuser || suisSuperutilisateur) &&
      role.permissions.every((code) => pouvoirs.has(code)),
  };
}
