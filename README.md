## Simple Bank CSV or others (versión modular)

Aplicación Streamlit para analizar transacciones bancarias desde un CSV
con categorización automática basada en reglas almacenadas en SQLite.

### Cómo ejecutar

1. Crear entorno virtual (opcional pero recomendado):

```bash
python -m venv .venv
.\.venv\Scripts\activate  # Windows
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Ejecutar la app:

```bash
streamlit run app.py
```

La primera vez que se ejecuta:
- Se crea `categories.db` (SQLite).
- Si existe un `categories.json` antiguo, se intentan migrar sus categorías y keywords.

