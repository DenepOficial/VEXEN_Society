# VEXEN Society v1.9.0 · Dashboard Control + Discord Logs

- Añade una cola segura `society_control_jobs` compartida con VEXEN Society Dashboard.
- El bot oficial consume y ejecuta las operaciones administrativas con `discord.py` y `SpaceService`.
- Soporta creación/eliminación, sincronización/reparación, bienvenida, canales personalizados, Staff, configuración global y roles autorizados.
- Las solicitudes aprobadas por el Dashboard pueden crear automáticamente la Society y respetar la selección inicial de canales de plantilla.
- Añade reintentos, recuperación de jobs interrumpidos, resultados persistentes y heartbeat del puente de control.
- Añade sistema de logs de auditoría en Discord basado en `audit_logs`.
- Nuevo `/society config canal_logs` para seleccionar o desactivar el canal de logs.
- Nuevo `/society config probar_logs` para validar que el bot puede publicar en el canal configurado.
- El canal de logs también puede seleccionarse visualmente desde Gestión de Society → Configuración.
- Las operaciones administrativas del Dashboard que antes no generaban auditoría ahora registran sus acciones.
- Si el canal de logs desaparece o pierde permisos, la operación principal del bot no se bloquea.
- No expone el token del bot al navegador y no duplica un segundo Gateway bot.
