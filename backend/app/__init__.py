import sys
from pathlib import Path

# Permite `import ml.busqueda` (la carpeta ml/ vive junto a backend/ en el monorepo)
_RAIZ = str(Path(__file__).resolve().parents[2])
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
