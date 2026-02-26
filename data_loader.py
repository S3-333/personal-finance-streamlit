from typing import IO, Set

import pandas as pd
import streamlit as st

from utils import ensure_datetime_column

# Columnas obligatorias que exigimos al CSV
REQUIRED_COLUMNS: Set[str] = {"Date", "Amount", "Details", "Debit/Credit"}


def validate_columns(df: pd.DataFrame) -> None:
    """
    Valida que el DataFrame tiene las columnas obligatorias.
    Lanza ValueError con mensaje claro si falta alguna.
    """
    cols = set(df.columns)
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise ValueError(
            f"El CSV no contiene las columnas obligatorias: {', '.join(sorted(missing))}"
        )


@st.cache_data(show_spinner=False)
def load_transactions(file: IO[bytes]) -> pd.DataFrame:
    """
    Carga el CSV desde un file-like object (Streamlit file_uploader),
    valida columnas y normaliza tipos.

    Se cachea con st.cache_data para evitar recargas innecesarias
    mientras el archivo no cambie.
    """
    df = pd.read_csv(file)

    # Normalizamos nombres de columnas (quitamos espacios alrededor)
    df.columns = [col.strip() for col in df.columns]

    # Validación robusta de columnas
    validate_columns(df)

    # Normalización de Amount: soporta tanto string con comas como números
    if pd.api.types.is_numeric_dtype(df["Amount"]):
        df["Amount"] = df["Amount"].astype(float)
    else:
        df["Amount"] = (
            df["Amount"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace(" ", "", regex=False)
            .astype(float)
        )

    # Normalización de Date → datetime
    df["Date"] = ensure_datetime_column(df, "Date")

    # Normalización de Debit/Credit
    df["Debit/Credit"] = (
        df["Debit/Credit"].astype(str).str.strip().str.title()
    )

    return df

