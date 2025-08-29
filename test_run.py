#!/usr/bin/env python3
"""Test script to verify Scarfy functionality"""

import sys
import asyncio
from pathlib import Path

# Add src to path to import our module
sys.path.insert(0, str(Path(__file__).parent / "src"))

from scarfy.main import main

if __name__ == "__main__":
    # Test manual mode
    sys.argv = ["test_run.py", "--manual"]
    print("Testing manual mode...")
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error in manual mode: {e}")
        import traceback

        traceback.print_exc()
