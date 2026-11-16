"""Project paths and local environment loading."""

from datetime import datetime
import os
from pathlib import Path
import tempfile

from dotenv import load_dotenv

# Package root used to locate the project resources.
base_dir = Path(__file__).resolve().parents[1]
# project_dir = base_dir.parent
# Project root used to resolve raw data and results.
project_dir = Path("/Users/yishai/Desktop/epigenetics_field_theory")
# Data input root
full_data_dir = project_dir / "data"
# Synthetic/demo input root selected when DEMO_MODE is true.
demo_data_dir = project_dir / "demo_data"
# Root for experiment outputs.
results_dir = project_dir / "results"


# Environment file loaded before app.config.config reads workflow switches.
env_dir = Path(__file__).with_name(".env")
# Matplotlib cache directory used to avoid writing its cache into the project.
mplconfig_dir = Path(tempfile.gettempdir()) / "epigenetics-field-theory-mplconfig"


def get_run_date() -> str:
    """Return the current local date formatted as day, month, and two-digit year."""
    return datetime.now().strftime("%d%m%y")


load_dotenv(dotenv_path=env_dir)
mplconfig_dir.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(mplconfig_dir)

# Selects demo input and output roots when true.
DEMO_MODE = os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes"}
# Notebook 2 reads this switch to bypass batch correction when true.
SKIP_BATCH_CORRECTION = os.getenv("skip_batch_correction", "True").strip().lower() in {
    "1",
    "true",
    "yes",
}
# Notebook 2 balances GFP-high samples after z-scoring when true.
SUBSAMPLE = os.getenv("subsample", "false").strip().lower() in {"1", "true", "yes"}
# Active data root selected using DEMO_MODE.
DATA_DIR = demo_data_dir if DEMO_MODE else full_data_dir

# Date label used by default for experiment output folders.
RUN_DATE = os.getenv("RUN_DATE") or get_run_date()
# Experiment output root; demo output is isolated from full-run output.
OUTPUT_ROOT = (
    results_dir / "demo" / f"experiment_{RUN_DATE}"
    if DEMO_MODE
    else results_dir / f"experiment_{RUN_DATE}"
)
# Shared annotation sidecar consumed during cell selection.
ANNOTATION_FILE = results_dir / "cell_annotations.csv"

# Notebook used as the source reference for extracted behavior.
SOURCE_REFERENCE = Path(os.getenv("SOURCE_REFERENCE") or "main1.ipynb").expanduser()
if not SOURCE_REFERENCE.is_absolute():
    SOURCE_REFERENCE = project_dir / SOURCE_REFERENCE
SOURCE_REFERENCE = SOURCE_REFERENCE.resolve()

__all__ = [
    "DEMO_MODE",
    "OUTPUT_ROOT",
    "RUN_DATE",
    "SKIP_BATCH_CORRECTION",
    "SUBSAMPLE",
    "SOURCE_REFERENCE",
    "base_dir",
    "DATA_DIR",
    "full_data_dir",
    "demo_data_dir",
    "env_dir",
    "get_run_date",
    "mplconfig_dir",
    "project_dir",
    "results_dir",
]
