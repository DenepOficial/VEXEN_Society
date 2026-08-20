# VEXEN Society v1.7.2

## Emoji personalizado en el nombre del asociado

Si `nombre` contiene un emoji personalizado de Discord, Society ahora
conserva dos representaciones:

- **Incorporación / Onboarding:** mantiene el nombre original y su emoji.
- **Categoría Society:** elimina únicamente el markup del emoji personalizado.

Ejemplo:

Nombre registrado:
`<:logo:1538690277991120938> Prueba`

Incorporación:
`[emoji] Prueba`

Categoría:
`👥 { VXS } { Prueba } { LosPoPis }`

El valor original almacenado en PostgreSQL no se modifica, por lo que
Onboarding sigue recibiendo exactamente el `display_name` registrado.

También soporta emojis personalizados animados con formato `<a:nombre:id>`.

Si el campo nombre contiene únicamente el emoji y ningún texto, se detiene
la creación porque la categoría necesita un nombre legible.
