# VEXEN Society v1.4

## Bienvenida
- `🎉 ¡BIENVENIDOS A VEXEN SOCIETY!` se muestra fuera del embed.
- Se envía como encabezado Markdown H1: `# 🎉 ¡BIENVENIDOS A VEXEN SOCIETY!`.
- El embed queda sin `title` y conserva descripción, color, footer y botón.

## Anuncios
- El CTA se controla por `associate_user_id`, nunca de forma global.
- Cada asociado mantiene como máximo un CTA visible bajo su anuncio más reciente.
- Un nuevo anuncio elimina únicamente el CTA anterior del mismo asociado.
- Otros asociados conservan sus propios CTA intactos.
- Si se borra el anuncio con CTA, el botón se recupera en el anuncio anterior existente del mismo asociado.
- Al iniciar, se intentan limpiar CTA duplicados antiguos de v1.3 por asociado.
