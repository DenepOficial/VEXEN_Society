# VEXEN Society v1.7

## Integración con Discord Community Onboarding

- Nuevo comando: `/society config incorporacion`.
- El parámetro `pregunta` usa autocompletado con las preguntas reales del Onboarding.
- Al configurarlo se sincronizan las Society activas existentes.
- Cada Society crea una respuesta usando `nombre` (display_name del comando), no el username de Discord ni el nombre de comunidad.
- La respuesta asigna `INT-{Comunidad}`.
- Si existe una opción manual antigua con el nombre del asociado/comunidad que otorgaba el rol final de esa misma Society, el sincronizador puede migrarla a INT de forma segura.
- Las demás preguntas y respuestas del Onboarding se conservan.
- Al crear nuevas Society se añade/actualiza automáticamente su opción.
- Al eliminar una Society se elimina su opción antes de borrar el rol INT.
- `/society config estado` muestra la pregunta configurada y cuántas opciones Society reconoce.
- `/society help` incluye el nuevo comando.
- Requisito mínimo actualizado a `discord.py>=2.6,<3`.

Los botones `Unirme a {Comunidad}` de bienvenida/anuncios mantienen su comportamiento actual: entregan el rol final de comunidad directamente. La nueva lógica INT aplica a la opción de incorporación de Discord.
