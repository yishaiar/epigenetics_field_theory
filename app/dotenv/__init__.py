"""Project paths and local environment loading."""

from datetime import datetime
import os
from pathlib import Path
import tempfile

from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parents[1]
project_dir = base_dir.parent
data_dir = project_dir / "raw_data"
demo_data_dir = project_dir / "demo_data" / "raw_data"
results_dir = project_dir / "results"
env_dir = Path(__file__).with_name(".env")
mplconfig_dir = Path(tempfile.gettempdir()) / "epigenetics-field-theory-mplconfig"


def get_run_date() -> str:
    """Return the current local date formatted as day, month, and two-digit year."""
    return datetime.now().strftime("%d%m%y")


load_dotenv(dotenv_path=env_dir)
mplconfig_dir.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(mplconfig_dir)

DEMO_MODE = os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes"}
active_data_dir = demo_data_dir if DEMO_MODE else data_dir

RUN_DATE = os.getenv("RUN_DATE") or get_run_date()
OUTPUT_ROOT = (
    results_dir / "demo" / f"experiment_{RUN_DATE}"
    if DEMO_MODE
    else results_dir / f"experiment_{RUN_DATE}"
)
ANNOTATION_FILE = results_dir / "cell_annotations.csv"

SOURCE_REFERENCE = Path(os.getenv("SOURCE_REFERENCE") or "main1.ipynb").expanduser()
if not SOURCE_REFERENCE.is_absolute():
    SOURCE_REFERENCE = project_dir / SOURCE_REFERENCE
SOURCE_REFERENCE = SOURCE_REFERENCE.resolve()

__all__ = [
    "DEMO_MODE",
    "OUTPUT_ROOT",
    "RUN_DATE",
    "SOURCE_REFERENCE",
    "base_dir",
    "active_data_dir",
    "data_dir",
    "demo_data_dir",
    "env_dir",
    "get_run_date",
    "mplconfig_dir",
    "project_dir",
    "results_dir",
]
