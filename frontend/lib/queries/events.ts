import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";
import type { EventPage, ParticipationFilters } from "@/lib/types";

export const EVENTS_PAGE_SIZE = 30;

/** Liste paginée d'épreuves pour le scroll infini. `initialData` = page 1 SSR. */
export function useInfiniteEvents(
  filters: ParticipationFilters = {},
  initialData?: EventPage,
) {
  return useInfiniteQuery({
    queryKey: queryKeys.events(filters),
    queryFn: ({ pageParam }) =>
      apiClient.listEvents({ ...filters, page: pageParam, page_size: EVENTS_PAGE_SIZE }),
    initialPageParam: 1,
    getNextPageParam: (lastPage, allPages) => {
      // total_events connu → on s'arrête dès que tout est chargé (pas de requête vide superflue).
      const loaded = allPages.reduce((sum, p) => sum + p.items.length, 0);
      return loaded < lastPage.total_events ? allPages.length + 1 : undefined;
    },
    initialData: initialData
      ? { pages: [initialData], pageParams: [1] }
      : undefined,
  });
}

/**
 * Participants d'une épreuve, chargés à la demande.
 * On rejoue les filtres club + nom pour rester cohérent avec les compteurs.
 */
export function useCourseParticipations(
  courseId: number,
  filters: Pick<ParticipationFilters, "club" | "name"> = {},
) {
  return useQuery({
    queryKey: queryKeys.courseParticipations(courseId, filters.club, filters.name),
    queryFn: () =>
      apiClient.listParticipations({
        course_id: courseId,
        club: filters.club,
        name: filters.name,
        page_size: 1000,
      }),
  });
}
