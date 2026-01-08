"""
Enable running JobScout as a module: python -m jobscout
"""

import sys
from jobscout.cli import main

if __name__ == "__main__":
    sys.exit(main())
