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
    parser.add_argument('-u', required=False)
    args = parser.parse_args()
    if args.command == 'upload' and args.u and os.path.exists(args.u):
        root = create_folder("SaveHaven")
        file_name = args.u.split('/')[-1] + '.zip'
        upload_file(args.u, file_name, root, os.path.isdir(args.u))
    if args.command == "sync":
        sync()

if __name__ == '__main__':
    main()