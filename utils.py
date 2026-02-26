import re
from typing import Optional

import pandas as pd


def normalize_text(text: str) -> str:
    """
    Normaliza texto para comparación:
    - Convierte a minúsculas
    - Elimina espacios iniciales/finales
    """
    return str(text).strip().lower()


def extract_keyword_from_details(details: str) -> Optional[str]:
    """
    Intenta extraer un "merchant name" o palabra clave razonable
    desde la columna Details, evitando guardar el texto completo.

    Heurística simple:
    - Dividir por espacios
    - Quitar tokens muy cortos o que son solo números
    - Devolver la palabra más larga razonable
    """
    if not details:
        return None

    tokens = re.split(r"\s+", str(details).strip())
    candidates = [
        t
        for t in tokens
        if len(t) >= 3 and not re.fullmatch(r"\d+(\.\d+)?", t)
    ]

    if not candidates:
        return None

    best = max(candidates, key=len)
    return best.upper()


def ensure_datetime_column(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Asegura que una columna está en formato datetime.
    Fija el resultado en el DataFrame y lo devuelve.
    """
    df[col] = pd.to_datetime(df[col], errors="coerce")
    return df[col]

