"""One-command local startup: `python run.py`.

Ensures the local database exists, then launches the
Streamlit app.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.database import init_db


def main() -> None:
    init_db()
    app_path = Path(__file__).resolve().parent / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path),
                    "--server.address", "127.0.0.1"], check=True)


if __name__ == "__main__":
    main()
