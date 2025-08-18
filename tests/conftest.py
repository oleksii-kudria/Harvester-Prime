from __future__ import annotations

import sys
from pathlib import Path


# Ensure project root is on the import path so ``scripts`` modules can be imported.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

