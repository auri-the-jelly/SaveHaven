from __future__ import print_function

from datetime import datetime

import os
import argparse
from helpers import *

def main():
    parser = argparse.ArgumentParser(
                    prog = 'SaveHaven',
                    description = 'Upload and sync video game files with Google Drive')
    
    commands = parser.add_subparsers(title='commands', dest='command')

    sync_parser = commands.add_parser('sync', help='Sync saves with Google Drive')
    
    upload_parser = commands.add_parser('upload', help='Upload path to google drive')
    upload_parser.add_argument('path', type=str, help='Path to upload')

    args = parser.parse_args()
    if args.command == 'upload' and args.path and os.path.exists(args.path):
        root = create_folder("SaveHaven")
        file_name = args.path.split('/')[-1] + '.zip'
        upload_file(args.path, file_name, root, os.path.isdir(args.path))
    elif args.command == "sync":
        sync()
    else: parser.print_help()

if __name__ == '__main__':
    main()