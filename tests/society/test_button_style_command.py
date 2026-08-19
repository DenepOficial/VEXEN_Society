from pathlib import Path


def test_style_commands_are_separate():
    text = (Path(__file__).resolve().parents[2]/"app"/"society"/"associates.py").read_text(encoding="utf-8")
    assert 'name="estilo_boton_bienvenida"' in text
    assert 'name="estilo_boton_anuncios"' in text
    assert 'name="estilo_boton_comunidad"' not in text
    assert 'name="primary — Azul"' in text
    assert 'name="secondary — Gris / oscuro"' in text
    assert 'name="success — Verde"' in text
    assert 'name="danger — Rojo"' in text
