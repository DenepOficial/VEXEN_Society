# VEXEN Society v1.3

## Botón de comunidad en anuncios globales

- El anuncio global continúa usando webhook para mostrar el nombre y avatar del autor original.
- Debajo del anuncio, VEXEN Society publica: `✨ ¿Quieres formar parte de {COMUNIDAD}?`
- Incluye el botón verde `✨ Unirme a esta comunidad`.
- Al pulsarlo, Society asigna el rol de comunidad y responde de forma privada con `🚪 Ir a la comunidad`.
- Los botones son persistentes y se restauran tras reiniciar el bot.
- Si el anuncio original se edita, se reemplazan el anuncio global y su mensaje de acceso.
- Si el anuncio original se elimina, ambos mensajes globales se eliminan.
- PostgreSQL migra automáticamente `announcement_mirrors` agregando `join_message_id`.
