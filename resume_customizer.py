#!/usr/bin/env python3
"""
Simple wrapper script to invoke the resume customizer module.

Usage:
    python resume_customizer.py --job_id <job_id> --output <output_filename.pdf> --pdf
"""

import sys
import os
import argparse

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the actual customizer module
from modules.resume.ai_resume_customizer import main as run_customizer

if __name__ == "__main__":
    run_customizer()
