"""Desktop entry point; keep this file for the existing run command."""

import os
import runpy
import sys


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
runpy.run_module("modi_flappy.desktop", run_name="__main__")
