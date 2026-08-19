# VEXEN Society v1.7.1 Hotfix

Corrige `/society config estado` cuando Discord Onboarding tarda más de
3 segundos en responder.

Antes, el comando hacía todas las consultas y solo después intentaba
responder a la interacción. Discord invalida una interacción si no recibe
una respuesta inicial a tiempo, produciendo:

`404 Not Found (error code: 10062): Unknown interaction`

Ahora el comando:
1. valida permisos;
2. hace `interaction.response.defer(ephemeral=True, thinking=True)`;
3. consulta PostgreSQL, VEXMOD y Onboarding;
4. devuelve el resultado mediante `interaction.followup.send(...)`.

No requiere cambios manuales en PostgreSQL ni en `.env`.
