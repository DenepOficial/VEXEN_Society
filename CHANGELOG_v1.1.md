# VEXEN Society v1.1

Cambios aplicados sobre v1.0:

- Canales de texto con separador exacto, por ejemplo `💬┃general`.
- Jerarquía forzada de roles: `Staff-Comunidad` > `Comunidad` > `INT-Comunidad`.
- Posición automática de categorías Society:
  - después de la última categoría que contenga `{ VXS }`;
  - si no existe, después de la categoría base configurada;
  - si no hay configuración, usa `COMUNIDAD` como respaldo.
- Nuevo comando `/society config categoria_base`.
- Anuncios Society reenviados mediante forward nativo de Discord, sin embed intermedio.
- Nuevo canal de bienvenida configurable con `/society config canal_bienvenida`.
- Embed de bienvenida amarillo/dorado `#F1C40F` con título grande.
- Botón público `🤝 Obtener rol de comunidad`.
- Tras obtener el rol, respuesta ephemeral con `🚪 Ir a la comunidad`.
- Los botones de comunidad se restauran automáticamente después de reiniciar el bot.
- Al eliminar una Society, el botón de la publicación de bienvenida queda desactivado.
- Migraciones idempotentes para bases v1.0 existentes.
