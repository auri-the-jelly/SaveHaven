#!/usr/bin/python3
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
from datetime import datetime

import os
import argparse, argcomplete
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

    list_parser = commands.add_parser(
        "list", help="List games from cloud and set to keep revisions forever"
    )

    cfg_parser = commands.add_parser("updatecfg", help="Update config with launchers")

    custom_parser = commands.add_parser("add", help="Add a custom game location")
    custom_parser.add_argument("name", help="Name of the game")
    custom_parser.add_argument("path", help="Path to upload")

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    match args.command:
        case "upload":
            if args.path and os.path.exists(args.path):
                root = create_folder("SaveHaven")
                if not args.name:
                    file_a = args.path.split("/")[-1]
                    file_b = args.path.split("/")[-2]
                    file_name = (file_a if file_a or file_a == "/" else file_b) + ".zip"
                else:
                    file_name = args.name
                upload_file(args.path, file_name, root, os.path.isdir(args.path))
        case "sync":
            sync(args.p, args.o)
        case "updatecfg":
            update_launchers()
        case "list":
            list_cloud()
        case "add":
            add_custom(args.name, args.path)
        case _:
            parser.print_help()


if __name__ == "__main__":
    main()
