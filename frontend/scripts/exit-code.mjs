// Code de sortie que le lanceur de dev rend à son appelant (npm, Task, superviseur).
//
// Le lanceur enveloppe `next dev` : son propre code doit donc parler de l'enfant,
// pas de lui-même. Un « 1 » forfaitaire dès que l'enfant meurt d'un signal se lit
// comme une panne applicative, alors que `pkill` sur `next dev` ou un OOM-kill n'en
// sont pas — d'où la convention shell 128+n (143 pour SIGTERM, 137 pour SIGKILL).
//
// Cas Ctrl-C, à ne pas confondre : SIGINT frappe tout le groupe de processus, donc
// le lanceur lui-même, qui meurt du signal sans passer par ici — l'appelant voit
// déjà 130. Ce chemin-ci ne sert qu'aux signaux visant le seul enfant.

import { constants } from "node:os";

/** Code à rendre pour un enfant sorti avec `code` / tué par `signal`. */
export function wrapperExitCode(code, signal) {
  if (signal) {
    const numero = constants.signals[signal];
    return numero ? 128 + numero : 1;
  }
  return code ?? 0;
}
