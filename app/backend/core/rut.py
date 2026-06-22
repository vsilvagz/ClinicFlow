"""Utilidad para normalizar un RUT escrito por el usuario.

El sistema identifica a las personas por su RUN como entero (sin dígito
verificador). Esta función acepta las formas habituales en que alguien escribe
un RUT y devuelve solo el número.
"""


def parsear_run(valor: str | None) -> int | None:
    """Normaliza un RUT a entero (sin dígito verificador).

    Acepta formas como "12.345.678-9" o "12345678": descarta puntos, espacios y
    el dígito verificador tras el guion. Devuelve None si no queda un número.
    """
    if not valor:
        return None
    limpio = valor.strip().split("-")[0].replace(".", "").replace(" ", "")
    return int(limpio) if limpio.isdigit() else None
