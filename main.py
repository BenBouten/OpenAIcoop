"""Entry point for the evolution simulation."""

import sys

from evolution.config import settings
from evolution.simulation import run


if __name__ == "__main__":
    runtime_settings = settings.load_runtime_settings(sys.argv[1:])
    settings.apply_runtime_settings(runtime_settings)
    run(runtime_settings)
