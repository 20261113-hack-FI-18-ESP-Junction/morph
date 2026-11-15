"""Install the same guards in the reviewed export-audit CLI subprocesses."""
import os

if os.environ.get("MORPH_OFFLINE_GUARD") == "1":
    from offline_guard import install
    install()
