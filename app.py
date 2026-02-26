import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import load_transactions
from storage import (
    init_db,
    get_categories_with_keywords,
    add_category,
    delete_category,
    add_keyword,
    delete_keyword,
    toggle_keyword_enabled,
    get_category_id_by_name,
)
from categorization import categorize_transactions
from utils import extract_keyword_from_details


st.set_page_config(
    page_title="Simple Bank CSV or others",
    page_icon="💰",
    layout="wide",
)


def ensure_db_initialized() -> None:
    """
    Inicializa la base de datos la primera vez que se carga la app.
    """
    if "db_initialized" not in st.session_state:
        init_db()
        st.session_state.db_initialized = True


def show_kpi_cards(df: pd.DataFrame, currency_symbol: str) -> None:
    """
    Muestra tarjetas KPI:
    - Total gastos (Debits)
    - Total ingresos (Credits)
    - Balance (ingresos - gastos)
    """
    debits = df[df["Debit/Credit"] == "Debit"]["Amount"].sum()
    credits = df[df["Debit/Credit"] == "Credit"]["Amount"].sum()
    balance = credits - debits

    col1, col2, col3 = st.columns(3)
    col1.metric("Total gastos", f"{currency_symbol}{debits:,.2f}")
    col2.metric("Total ingresos", f"{currency_symbol}{credits:,.2f}")
    col3.metric("Balance", f"{currency_symbol}{balance:,.2f}")


def apply_filters(
    df: pd.DataFrame,
    start_date,
    end_date,
    selected_categories,
) -> pd.DataFrame:
    """
    Aplica filtros de rango de fechas y categorías sobre el DataFrame.
    """
    if start_date:
        df = df[df["Date"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["Date"] <= pd.to_datetime(end_date)]
    if selected_categories:
        df = df[df["Category"].isin(selected_categories)]
    return df


def show_expense_charts(df: pd.DataFrame, currency_symbol: str) -> None:
    """
    Muestra gráficos:
    - Pie chart por categoría
    - Línea mensual de gastos
    - Gastos por categoría en el tiempo
    """
    category_totals = (
        df[df["Debit/Credit"] == "Debit"]
        .groupby("Category")["Amount"]
        .sum()
        .reset_index()
        .sort_values("Amount", ascending=False)
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Distribución de gastos por categoría")
        fig_pie = px.pie(
            category_totals,
            names="Category",
            values="Amount",
            title="Gastos por categoría",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.subheader("Gasto mensual total")
        monthly = (
            df[df["Debit/Credit"] == "Debit"]
            .set_index("Date")
            .resample("M")["Amount"]
            .sum()
            .reset_index()
        )
        if not monthly.empty:
            fig_line = px.line(
                monthly,
                x="Date",
                y="Amount",
                title="Gasto mensual",
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No hay datos de gastos para mostrar en el tiempo.")

    st.subheader("Gastos por categoría en el tiempo")
    category_time = df[df["Debit/Credit"] == "Debit"].copy()
    if not category_time.empty:
        category_time["Month"] = (
            category_time["Date"].dt.to_period("M").dt.to_timestamp()
        )
        grouped = (
            category_time.groupby(["Month", "Category"])["Amount"]
            .sum()
            .reset_index()
        )
        fig_cat_time = px.line(
            grouped,
            x="Month",
            y="Amount",
            color="Category",
            title="Gastos por categoría en el tiempo",
        )
        st.plotly_chart(fig_cat_time, use_container_width=True)
    else:
        st.info("No hay datos de gastos por categoría para mostrar.")


def show_category_management() -> None:
    """
    Configuración en la barra lateral para:
    - Ver categorías y sus keywords
    - Añadir/eliminar categorías
    - Añadir/eliminar keywords
    - Activar/desactivar keywords
    """
    st.sidebar.subheader("Configuración de categorías")

    categories = get_categories_with_keywords()

    with st.sidebar.expander("Añadir categoría"):
        new_cat_name = st.text_input("Nombre de categoría", key="new_category_name")
        new_cat_priority = st.number_input(
            "Prioridad (menor = más importante)",
            min_value=1,
            max_value=999,
            value=100,
            step=1,
            key="new_category_priority",
        )
        if st.button("Crear categoría", key="create_category_btn"):
            if new_cat_name.strip():
                add_category(new_cat_name.strip(), int(new_cat_priority))
                st.success(f"Categoría '{new_cat_name}' creada.")
                st.rerun()
            else:
                st.warning("El nombre de la categoría no puede estar vacío.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Categorías existentes")

    for cat in categories:
        is_uncategorized = cat["name"] == "Uncategorized"

        with st.sidebar.expander(f"{cat['name']} (prioridad {cat['priority']})"):
            if not is_uncategorized:
                if st.button(
                    "Eliminar categoría",
                    key=f"delete_cat_{cat['id']}",
                    help="Elimina la categoría y todas sus keywords.",
                ):
                    delete_category(cat["id"])
                    st.rerun()

            st.write("Keywords / patrones:")
            for kw in cat["keywords"]:
                cols = st.columns([3, 1, 1])
                cols[0].write(
                    f"{'[REGEX] ' if kw['is_regex'] else ''}{kw['pattern']}"
                )

                checked = cols[1].checkbox(
                    "On",
                    value=kw["enabled"],
                    key=f"kw_enabled_{kw['id']}",
                )
                if checked:
                    if not kw["enabled"]:
                        toggle_keyword_enabled(kw["id"], True)
                else:
                    if kw["enabled"]:
                        toggle_keyword_enabled(kw["id"], False)

                if cols[2].button("🗑", key=f"del_kw_{kw['id']}"):
                    delete_keyword(kw["id"])
                    st.rerun()

            st.write("Añadir keyword / patrón:")
            new_kw = st.text_input(
                "Texto o regex",
                key=f"new_kw_{cat['id']}",
            )
            as_regex = st.checkbox(
                "Interpretar como regex",
                key=f"new_kw_regex_{cat['id']}",
            )
            if st.button("Añadir keyword", key=f"add_kw_btn_{cat['id']}"):
                if new_kw.strip():
                    add_keyword(cat["id"], new_kw.strip(), is_regex=as_regex)
                    st.success("Keyword añadida.")
                    st.rerun()
                else:
                    st.warning("La keyword no puede estar vacía.")


def main() -> None:
    ensure_db_initialized()

    st.title("Simple Bank CSV or others")

    st.sidebar.header("Filtros")

    currency_symbol = st.sidebar.selectbox(
        "Moneda",
        options=["AED", "USD", "EUR"],
        index=0,
    )
    currency_symbol_map = {"AED": "AED ", "USD": "$", "EUR": "€"}
    symbol = currency_symbol_map.get(currency_symbol, "")

    show_category_management()

    st.markdown("### Carga de archivo CSV")
    uploaded_file = st.file_uploader("Sube un archivo CSV", type=["csv"])

    if uploaded_file is None:
        st.info("Sube un CSV para comenzar el análisis.")
        return

    try:
        df_raw = load_transactions(uploaded_file)
    except ValueError as e:
        st.error(str(e))
        return
    except Exception as e:
        st.error(f"Error inesperado al cargar el CSV: {e}")
        return

    df = categorize_transactions(df_raw)
    st.session_state["transactions_df"] = df

    min_date = df["Date"].min().date()
    max_date = df["Date"].max().date()

    date_range = st.sidebar.date_input(
        "Rango de fechas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    unique_categories = sorted(df["Category"].unique().tolist())
    selected_categories = st.sidebar.multiselect(
        "Filtrar por categorías",
        options=unique_categories,
        default=unique_categories,
    )

    filtered_df = apply_filters(df, start_date, end_date, selected_categories)

    show_kpi_cards(filtered_df, symbol)

    tab1, tab2 = st.tabs(["Análisis de gastos", "Configuración avanzada"])

    with tab1:
        st.subheader("Tabla de transacciones (gastos)")

        debits_df = filtered_df[filtered_df["Debit/Credit"] == "Debit"].copy()

        edited_df = st.data_editor(
            debits_df[["Date", "Details", "Amount", "Category"]],
            column_config={
                "Date": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                "Amount": st.column_config.NumberColumn(
                    "Importe", format=f"{symbol}%.2f"
                ),
                "Category": st.column_config.SelectboxColumn(
                    "Categoría",
                    options=unique_categories,
                    required=True,
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="debits_editor",
        )

        if st.button("Aplicar cambios y aprender nuevas keywords", type="primary"):
            merged = debits_df[["Details", "Category"]].copy()
            merged["NewCategory"] = edited_df["Category"].values

            changed = merged[merged["Category"] != merged["NewCategory"]]

            if not changed.empty:
                for _, row in changed.iterrows():
                    details = row["Details"]
                    new_cat_name = row["NewCategory"]
                    keyword = extract_keyword_from_details(details)
                    if keyword:
                        cat_id = get_category_id_by_name(new_cat_name)
                        if cat_id is not None:
                            add_keyword(cat_id, keyword, is_regex=False)

                st.success(
                    "Cambios aplicados. Se han aprendido nuevas keywords a partir de tus ediciones."
                )
                st.rerun()
            else:
                st.info("No se detectaron cambios en categorías.")

        st.markdown("---")
        st.subheader("Resumen y gráficos")
        show_expense_charts(filtered_df, symbol)

    with tab2:
        st.subheader("Vista completa de transacciones")
        st.dataframe(
            filtered_df.sort_values("Date"),
            use_container_width=True,
        )


if __name__ == "__main__":
    main()

