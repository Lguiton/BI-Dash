"""Imports every advanced lab so they register themselves."""
import importlib

for _m in ("prolab_cpe", "prolab_fullstack", "prolab_pm", "prolab_sysanalyst", "prolab_ai", "prolab_ml", "prolab_de", "prolab_ds"):
    try:
        importlib.import_module(f"app.services.{_m}")
    except ModuleNotFoundError as _e:       # a lab not built yet is simply absent
        if _e.name != f"app.services.{_m}":
            raise
