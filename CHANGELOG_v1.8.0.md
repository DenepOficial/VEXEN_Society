# VEXEN Society v1.8.0

## Bienvenida manual por asociado

Nuevo comando administrativo:

`/society bienvenida reenviar asociado:@Usuario`

- Busca una Society activa por asociado.
- Publica nuevamente la bienvenida usando el canal, color y estilo de botón actuales.
- Mantiene el mensaje anterior, pero desactiva su botón una vez confirmada la nueva publicación.
- Guarda el nuevo mensaje como bienvenida activa y registra auditoría `WELCOME_REPUBLISHED`.

## Permisos Staff de comunidad

El overwrite local de `Staff-{Comunidad}` en la categoría Society ahora incluye los permisos aprobados para texto y voz, entre ellos menciones globales, gestión/fijado de mensajes, bypass de modo lento, encuestas, soundboard, prioridad de palabra, moderación de voz y estado del canal de voz.

No concede explícitamente Administrador, Gestionar canales, Gestionar permisos/roles, Gestionar webhooks, eventos, comandos/apps externas, TTS ni mensajes de voz.

Las Society existentes se reconcilian automáticamente una vez al iniciar el bot. Los canales `STAFF-TXT` y `STAFF-VOICE`, que tienen overwrite propio, también se actualizan. La sincronización manual de plantilla vuelve a aplicar estos permisos.

## Cambios de entorno conservados

- Schema Society por defecto: `vexen_society`.
- `.env.example` usa `SOCIETY_DB_SCHEMA=vexen_society`.
- `.gitignore` ignora `*.zip`.

## Dependencia

Se eleva `discord.py` a `>=2.7,<3` porque `pin_messages`, `bypass_slowmode` y `set_voice_channel_status` se incorporaron en discord.py 2.7.
