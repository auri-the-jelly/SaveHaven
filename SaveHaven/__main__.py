from __future__ import print_function

from datetime import datetime

import os
from helpers import *

def main():
    config = os.path.join(config_dir, 'config.ini')
    if not os.path.exists(config):
        print("Config file not found, running intialization")
        print("Select launchers (if not listed, add paths manually):")
        launchers = ['Steam', 'Heroic', "Epic Games Store w/ Wine", "GOG Galaxy"]
        for i in range(len(launchers)):
            print(f"{i + 1}. {launchers[i]}")

        while True:
            launcher_nums = input("Enter range (3-5) or indexes (1,3,5): ")
            valid_chars = "1234567890-,"
            valid = True
            for i in launcher_nums:
                if i not in valid_chars:
                    print("Invalid characters")
                    valid = False
                    break
                if i.isnumeric() and int(i) > len(launchers):
                    print("Index out of range")
                    valid = False
                    break
            if valid == False:
                continue
            if launcher_nums.count('-') > 1 or ('-' in launcher_nums and ',' in launcher_nums):
                print("Specify no more than range, or use list")
                continue
            try:
                if '-' in launcher_nums:
                    indices = range(int(launcher_nums.split('-')[0]), int(launcher_nums.split('-')[1]) + 1)

                elif ',' in launcher_nums:
                    indices = launcher_nums.split(',')

                elif len(launcher_nums) == 1:
                    indices = [int(launcher_nums)]

                elif launcher_nums == '':
                    indices = range(1, len(launchers) + 1)

                print("Selecting these launchers: ")
                for i in range(len(indices)):
                    indices[i] = int(indices[i]) - 1
                selected_launchers = [x for x in launchers if launchers.index(x) in indices]
                update_launchers(selected_launchers)
                print(selected_launchers)
                break
            except Exception as e:
                print("Error occured: ", e)

    # If SaveHaven folder doesn't exist, create it.
    folder = create_folder(filename="SaveHaven")
    print("Created " + folder)


    # Search for save file directories
    search_dir(folder)

if __name__ == '__main__':
    main()