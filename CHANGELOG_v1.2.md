# VEXEN Society v1.2

## Cambios

- Anuncios globales retransmitidos por webhook usando nombre y avatar del autor original.
- Adjuntos del anuncio se vuelven a subir al canal global; edición y eliminación siguen sincronizadas.
- El bot crea/reutiliza un webhook llamado `VEXEN Society Relay` en el canal global.
- Color predeterminado de bienvenida cambiado a `#57F287`.
- Nuevo `/society config color_bienvenida` con soporte para `#RRGGBB`, `RRGGBB` y `default`.
- Botón de bienvenida cambiado a verde: `✨ Unirme a esta comunidad`.
- Confirmación más cálida al obtener el rol y botón privado `🚪 Ir a la comunidad`.
- Corregida la sincronización de canales eliminados manualmente: reemplaza el binding viejo por `channel_key` y evita `UniqueViolationError`.
- La sincronización restaura el orden lógico de los canales de plantilla; texto y voz se ordenan por separado por limitación de Discord.
- Nuevo `/society help` con guía integrada de comandos.

## Permiso adicional

Para mostrar el nombre/avatar del remitente en anuncios globales, el bot necesita `Administrar webhooks` en el canal global de anuncios.
