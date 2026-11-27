import os
from pathlib import Path
from fastapi.templating import Jinja2Templates

# Obtén la ruta absoluta al directorio raíz (Lynko/)
# Si tu estructura es Lynko/Backend y Lynko/Frontend:
BASE_DIR = Path(__file__).resolve().parent  # D:\Lynko\Backend
TEMPLATES_DIR = BASE_DIR.parent / "Frontend" / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))