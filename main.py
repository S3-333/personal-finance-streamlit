"""
Entrada histórica de la aplicación.
Ahora delega en la nueva arquitectura modular ubicada en app.py.

Se mantiene este archivo para no romper comandos existentes como:
    streamlit run main.py
Pero toda la lógica de negocio y UI vive en app.py y en los módulos auxiliares.
"""

from app import main


if __name__ == "__main__":
    main()
