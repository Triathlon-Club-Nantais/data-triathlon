# Coucher de la preview, chaque heure à la minute 45 (#1319). Le cron horaire de
# `render-sleep.yml` sautait des heures entières (~7 passages sur 24 le 10/10) et
# a été retiré par #1157. Les gardes (déploiement en vol, délai de grâce)
# restent dans le workflow.
# Minute 45, pas 15 : `concurrency` ne garde qu'un run en attente, et un dispatch
# simultané au lever de 2 h 15 pourrait faire annuler celui de la production.
# Pas d'alerte Slack ici : un jeton en panne alerte déjà par la veille de la
# production, et une alerte par heure noierait le canal.
param($Timer)

Invoke-RenderSleep -Action suspend -Target preview
