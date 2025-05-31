#!/usr/bin/env python3
"""
Big NetScan - Professional Network Scanner
A modern GTK4 network scanner for discovering local devices and services.

Author: Professional Network Tools
License: GNU GPL v2
Python: 3.10+
Requirements: GTK4, Adwaita (ArchLinux packages)
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.gui.main_window import NetworkScannerApp


def main() -> None:
    """Main entry point for the network scanner application."""
    try:
        app = NetworkScannerApp()
        return app.run(sys.argv)
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
