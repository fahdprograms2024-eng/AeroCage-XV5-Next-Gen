#!/usr/bin/env python3
"""
File Name: bootstrapper.py
Purpose: Dynamic Path Injection to fix ModuleNotFoundError.
"""
import sys
import os

def verify_tactical_environment():
    """Checks and injects paths to ensure module imports work."""
    CURRENT_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
    if CURRENT_PROJECT_DIR not in sys.path:
        sys.path.insert(0, CURRENT_PROJECT_DIR)
    # Force reload if needed (optional, but good for dev)
    # import importlib
    # if 'repositories' in sys.modules: importlib.reload(sys.modules['repositories'])
