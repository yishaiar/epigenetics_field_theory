"""Project paths and local environment loading."""

from pathlib import Path
import os
import tempfile

from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parents[1]
project_dir = base_dir.parent
data_dir = project_dir / "raw_dats"
results_dir = project_dir / "results"
env_dir = Path(__file__).with_name("params.env")
mplconfig_dir = Path(tempfile.gettempdir()) / "epigenetics-field-theory-mplconfig"

load_dotenv(dotenv_path=env_dir)
mplconfig_dir.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(mplconfig_dir)

RUN_DATE = os.getenv("RUN_DATE", "141026")
OUTPUT_ROOT = results_dir / f"experiment_{RUN_DATE}"
SOURCE_REFERENCE = Path(os.getenv("SOURCE_REFERENCE") or "main1.ipynb").expanduser()
if not SOURCE_REFERENCE.is_absolute():
    SOURCE_REFERENCE = project_dir / SOURCE_REFERENCE
SOURCE_REFERENCE = SOURCE_REFERENCE.resolve()

__all__ = [
    "OUTPUT_ROOT",
    "RUN_DATE",
    "SOURCE_REFERENCE",
    "base_dir",
    "data_dir",
    "env_dir",
    "mplconfig_dir",
    "project_dir",
    "results_dir",
]
