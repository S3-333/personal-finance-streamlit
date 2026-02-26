import pandas as pd

from categorization import apply_rules_vectorized, CategoryRule


def test_apply_rules_vectorized_simple():
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "Details": ["COMPRA LULU HYPERMARKET", "PAGO NETFLIX"],
            "Amount": [100.0, 50.0],
            "Debit/Credit": ["Debit", "Debit"],
        }
    )

    rules = [
        CategoryRule(
            name="Supermercado",
            priority=1,
            patterns=["LULU"],
            is_regex_flags=[False],
        ),
        CategoryRule(
            name="Entretenimiento",
            priority=2,
            patterns=["NETFLIX"],
            is_regex_flags=[False],
        ),
    ]

    result = apply_rules_vectorized(df, rules)

    assert result.loc[0, "Category"] == "Supermercado"
    assert result.loc[1, "Category"] == "Entretenimiento"

