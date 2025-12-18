"""
Big Network Info - Professional Network Scanner
A modern GTK4 network scanner for discovering local devices and services.

License: GNU GPL v2
Python: 3.10+
"""

import os
import sys

# Performance optimization: Use OpenGL renderer instead of Vulkan
if "GSK_RENDERER" not in os.environ:
    os.environ["GSK_RENDERER"] = "gl"

if __package__ is None:
    import pathlib

    parent_dir = pathlib.Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    __package__ = "big_network_info"

__version__ = "1.0.0"
__app_id__ = "br.com.biglinux.networkinfo"


def main() -> int:
    """Main entry point for the network scanner application."""
    try:
        from .gui.main_window import NetworkScannerApp

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
