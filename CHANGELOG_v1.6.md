# VEXEN Society v1.6

- Se separa el estilo del botón de bienvenida y el de anuncios.
- `/society config estilo_boton_bienvenida`: solo afecta bienvenidas.
- `/society config estilo_boton_anuncios`: solo afecta CTA de anuncios.
- Valores predeterminados: bienvenida `success — Verde`; anuncios `secondary — Gris / oscuro`.
- Ambos comandos aceptan `primary`, `secondary`, `success` y `danger` con su color visible.
- Cada comando intenta actualizar también los botones ya publicados de su propio tipo.
- `/society config estado` muestra ambos estilos por separado.
- `/society help` incluye ambos comandos.
- La antigua columna `community_button_style` queda solo por compatibilidad y ya no dirige los botones en v1.6.
