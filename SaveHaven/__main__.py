from __future__ import print_function

from datetime import datetime

import os
import argparse
from helpers import *

def main():
    parser = argparse.ArgumentParser(
                    prog = 'SaveHaven',
                    description = 'Upload and sync video game files with Google Drive')
    parser.add_argument('command')
    args = parser.parse_args()
    if args.command == "sync":
        sync()

if __name__ == '__main__':
    main()