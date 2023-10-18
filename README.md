# SaveHaven
A CLI tool to backup video game save files, launcher agnostically

## Installation
    git clone https://github.com/RNKnight1/SaveHaven.git
    cd SaveHaven
    pip install -e .

Currently only supports Linux and Heroic launcher games.

## Working On

#### Currently
--------------

Minecraft

#### Planned
------------

Backup/Multiple instances

GOG and Legendary support

Emulator support

Nextcloud

Steam support

Multiple save files

#### Barely functional
----------------------
Heroic support

SQLite3 db to document syncs

Argparse

Custom directory support

#### Scrapped

Wine EGS - - Games are stored in different places for each game and games may not always use the prefix, and PCGamingWiki is not reliable enough for Linux games

## For those poor souls who stumbled upon this project and want to contribute for god knows why

#### Google Drive API
Follow these [instructions](https://developers.google.com/drive/api/quickstart/python) to set up a Google Cloud project, place the credentials.json in the config folder, then run quickstart.py to acquire token.

Now, you can make your changes to __main__.py and helpers.py
Thank you if you do, I admire your resolve.
