// État focalisé de toute entrée de menu ou de liste (#1305, #1308) : fond
// `--tcn-orange-08`, texte à l'encre héritée (14,7:1), trait opaque
// `--tcn-orange` posé à l'intérieur. Jamais d'`outline-hidden` ni
// d'`outline-none` à côté : en Tailwind 4 ils annulent `outline-2`.
// Hors de `dropdown-menu`, que `select` rembarquait sinon sur chaque page (#1603).
export const ITEM_FOCUS =
  "data-highlighted:bg-[var(--tcn-orange-08)] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--tcn-orange)]"
