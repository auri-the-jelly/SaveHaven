from datetime import datetime

import os
import argparse
from savehaven.helpers import *


def main():
    parser = argparse.ArgumentParser(
        prog="SaveHaven",
        description="Upload and sync video game files with Google Drive",
    )

    commands = parser.add_subparsers(title="commands", dest="command")

    sync_parser = commands.add_parser("sync", help="Sync saves with Google Drive")
    sync_parser.add_argument("-p", "--persistent", action="store_true", dest="p")
    sync_parser.add_argument("-o", "--overwrite", action="store_true", dest="o")

    upload_parser = commands.add_parser("upload", help="Upload path to google drive")
    upload_parser.add_argument("path", type=str, help="Path to upload")
    upload_parser.add_argument(
        "-n", "--name", type=str, help="Name of the zip to upload", required=False
    )

    list_parser = commands.add_parser("keepforever", help="List games from cloud")

    cfg_parser = commands.add_parser("updatecfg", help="Update config with launchers")

    args = parser.parse_args()
    if args.command == "upload" and args.path and os.path.exists(args.path):
        root = create_folder("SaveHaven")
        if not args.name:
            file_a = args.path.split("/")[-1]
            file_b = args.path.split("/")[-2]
            file_name = (file_a if file_a or file_a == "/" else file_b) + ".zip"
        else:
            file_name = args.name
        upload_file(args.path, file_name, root, os.path.isdir(args.path))
    elif args.command == "sync":
        sync(args.p, args.o)
    elif args.command == "updatecfg":
        update_launchers()
    elif args.command == "keepforever":
        list_cloud()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
