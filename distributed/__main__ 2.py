#!/usr/bin/env python3
"""Allow running distributed module as: python3 -m distributed"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
