# VEXEN Society v1.4.1 Hotfix

Corrige el fallo al iniciar:

`KeyError: 'source_message_id'`

La rutina de restauración/saneamiento de botones de anuncios necesita
`source_message_id` para limpiar CTA antiguos del mismo asociado, pero
la consulta SQL de `list_active_announcement_role_button_bindings()`
no lo incluía en el SELECT.

No requiere borrar ni modificar manualmente PostgreSQL.
Al iniciar, el bot puede continuar el saneamiento pendiente de los CTA
existentes de v1.3/v1.4.
