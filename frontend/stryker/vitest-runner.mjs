// Runner Stryker `vitest-gt` : le runner `vitest` publié, dont le filtre de
// noms de tests est rendu compatible avec vitest 5.
//
// shortcut: @stryker-mutator/vitest-runner 10.0.0 joint suite et test par une
// espace dans `testNamePattern`, vitest 5 compare à `fullTestName` joint par
// « > » (vitest/dist/task-utils.js) : tout test sous un `describe` était sauté,
// donc chaque mutant « Survived » sans test. Retirer ce fichier quand le runner
// joint les noms par « > ».
import { strykerPlugins as published } from "@stryker-mutator/vitest-runner";

const [vitest] = published;

function createRunner(injector) {
  const runner = vitest.factory(injector);
  const init = runner.init.bind(runner);
  runner.init = async () => {
    await init();
    for (const project of runner.ctx.projects) {
      let pattern;
      Object.defineProperty(project.config, "testNamePattern", {
        configurable: true,
        enumerable: true,
        get: () => pattern,
        set: (regex) => {
          pattern = regex && new RegExp(regex.source.replaceAll(" ", "(?: | > )"));
        },
      });
    }
  };
  return runner;
}
createRunner.inject = vitest.factory.inject;

export const strykerPlugins = [{ ...vitest, name: "vitest-gt", factory: createRunner }];
