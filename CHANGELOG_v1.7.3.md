# VEXEN Society v1.7.3

## Onboarding: emoji + opción automática corregidos

Discord Onboarding maneja el emoji de cada respuesta en un campo separado
del título. Society ahora interpreta correctamente:

`<:logo:1538690277991120938> Prueba`

como:

- Título de la opción: `Prueba`
- Emoji de la opción: `<:logo:1538690277991120938>`
- Rol asignado: `INT-{COMUNIDAD}`

La categoría continúa usando solo `Prueba`, tal como se corrigió en v1.7.2.

El valor original de `display_name` sigue intacto en PostgreSQL.

## Sincronización
- Al crear una Society, la opción se añade/actualiza automáticamente.
- Society verifica la respuesta devuelta por Discord después de modificar
  Onboarding; si Discord no confirma la opción, se reporta error.
- `/society config incorporacion` vuelve a sincronizar todas las Society
  activas, por lo que también repara una Society creada durante v1.7.2.

## Eliminación
- Al borrar el asociado, primero se elimina su opción de Onboarding por su
  rol `INT-{COMUNIDAD}`.
- Society verifica que Discord realmente la haya retirado.
- Si la eliminación de Onboarding falla, NO se borra el rol INT ni el resto
  de la Society. La operación queda bloqueada para poder reintentar sin dejar
  una opción huérfana.
