from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from utils import normalize_text
from storage import get_categories_with_keywords

try:
    from rapidfuzz import fuzz, process

    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False


@dataclass
class CategoryRule:
    """
    Regla de categorización para una categoría concreta.
    Agrupa varios patrones (regex o substring simple).
    """

    name: str
    priority: int
    patterns: List[str]
    is_regex_flags: List[bool]


def build_rules_from_storage() -> List[CategoryRule]:
    """
    Construye reglas de categorización a partir de la base de datos SQLite.
    La prioridad de la categoría define el orden: menor prioridad = se evalúa antes.
    """
    categories = get_categories_with_keywords()
    rules: List[CategoryRule] = []

    for cat in categories:
        if cat["name"] == "Uncategorized":
            continue

        enabled_keywords = [k for k in cat["keywords"] if k["enabled"]]
        if not enabled_keywords:
            continue

        patterns = [k["pattern"] for k in enabled_keywords]
        is_regex_flags = [k["is_regex"] for k in enabled_keywords]

        rules.append(
            CategoryRule(
                name=cat["name"],
                priority=cat["priority"],
                patterns=patterns,
                is_regex_flags=is_regex_flags,
            )
        )

    rules.sort(key=lambda r: r.priority)
    return rules


def apply_rules_vectorized(df: pd.DataFrame, rules: List[CategoryRule]) -> pd.DataFrame:
    """
    Aplica reglas de categorización de forma vectorizada usando pandas.
    Primera coincidencia gana (según prioridad de categoría).
    """
    df = df.copy()
    if "Category" not in df.columns:
        df["Category"] = "Uncategorized"

    details_norm = df["Details"].astype(str).str.lower().fillna("")

    for rule in rules:
        uncategorized_mask = df["Category"] == "Uncategorized"
        if not uncategorized_mask.any():
            break

        category_mask = pd.Series(False, index=df.index)

        for pattern, is_regex in zip(rule.patterns, rule.is_regex_flags):
            if not pattern:
                continue

            if is_regex:
                m = details_norm.str.contains(
                    pattern,
                    case=False,
                    regex=True,
                    na=False,
                )
            else:
                escaped = pattern.lower()
                m = details_norm.str.contains(
                    escaped,
                    case=False,
                    regex=False,
                    na=False,
                )

            category_mask |= m

        final_mask = uncategorized_mask & category_mask
        df.loc[final_mask, "Category"] = rule.name

    return df


def categorize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Función principal de categorización: construye reglas desde SQLite y las aplica.
    """
    rules = build_rules_from_storage()
    return apply_rules_vectorized(df, rules)


def fuzzy_categorize_single_details(
    details: str,
    candidate_categories: List[str],
    threshold: int = 80,
) -> Optional[str]:
    """
    Ejemplo avanzado opcional de fuzzy matching con rapidfuzz.
    No se usa en el flujo principal, pero queda disponible.
    """
    if not HAS_RAPIDFUZZ:
        return None

    text = normalize_text(details)
    if not text or not candidate_categories:
        return None

    best_match, score, _ = process.extractOne(
        text, candidate_categories, scorer=fuzz.token_sort_ratio
    )
    if score >= threshold:
        return best_match
    return None

