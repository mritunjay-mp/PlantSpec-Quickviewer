"""Import PlantSpec analysis engine without Tk GUI dependencies."""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "tkinter" not in sys.modules:
    tk = types.ModuleType("tkinter")
    ttk = types.ModuleType("tkinter.ttk")
    filedialog = types.ModuleType("tkinter.filedialog")
    messagebox = types.ModuleType("tkinter.messagebox")

    class _Tk:
        def __init__(self, *args, **kwargs):
            pass

        def title(self, *args, **kwargs):
            pass

        def geometry(self, *args, **kwargs):
            pass

        def mainloop(self, *args, **kwargs):
            pass

    tk.Tk = _Tk
    tk.END = "end"
    tk.BOTH = "both"
    tk.X = "x"
    tk.Y = "y"
    tk.LEFT = "left"
    tk.RIGHT = "right"
    tk.TOP = "top"
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.ttk"] = ttk
    sys.modules["tkinter.filedialog"] = filedialog
    sys.modules["tkinter.messagebox"] = messagebox

import plantspec_quickviewer as pq  # noqa: E402

__all__ = ["pq", "ROOT"]
