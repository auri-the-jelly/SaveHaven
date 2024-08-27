# region Imports
import os
import io
import json
import sqlite3
import requests
import configparser
import inquirer

from pyfzf.pyfzf import FzfPrompt
from datetime import datetime, timezone
from appdirs import user_config_dir, user_data_dir
from bs4 import BeautifulSoup
from shutil import make_archive, unpack_archive, move, copytree
from inquirer.themes import GreenPassion
from tqdm import tqdm

import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from savehaven.configs import creds


# endregion


# region Variables
SCOPES = ["https://www.googleapis.com/auth/drive"]
config_dir = user_config_dir("SaveHaven", "Aurelia")
backups_dir = os.path.join(config_dir, "Backups")
tmp_dir = os.path.join(config_dir, "tmp")
if not os.path.exists(config_dir):
    os.mkdir(config_dir)
    os.mkdir(backups_dir)
    os.mkdir(tmp_dir)
list_file = os.path.join(config_dir, "game_list.json")
home_path = os.path.expanduser("~")
games_dir = os.path.join(home_path, "Games")
heroic_dir = os.path.join(games_dir, "Heroic", "Prefixes")
heroic_saves = []
persistent = False
overwrite = False
# create drive api client
service = build("drive", "v3", credentials=creds)
fzf = FzfPrompt()
# endregion


# region Classes


class SaveDir:
    """
    Object to store name, path and modified time of a folder

    Attributes
    ----------
    name : str
        Name of the folder

    path: str
        Path of the folder

    modified: str
        Last modified time of folder
    """

    def __init__(self, name, path, modified):
        self.name = name
        self.path = path
        self.modified = modified

    def __str__(self):
        return f"Name: {self.name}\n Path: {self.path}\n Last modified: {self.modified}"


# endregion


# region Drive Functions
def mod_time(file_id: str) -> datetime:  # sourcery skip: do-not-use-bare-except
    """
    Returns when a given file was last modified

    Parameters
    ----------

    file_id: str
        ID of the Google Drive file

    Returns
    -------
    date_time_obj: datetime
        Datetime object of last modified time
    """
    try:
        file = service.files().get(fileId=file_id, fields="modifiedTime").execute()
        modified_time = file["modifiedTime"]
        return datetime.strptime(modified_time, "%Y-%m-%dT%H:%M:%S.%fZ")

    except:
        print("Failed")


def search_file(mime_type: str, filename: str) -> str:
    """
    Search for file in Google Drive

    Parameters
    ----------
    mime_type: str
        Mime type of the file

    filename: str
        Filename of Google Drive file

    Returns
    -------
    file_id: str
        ID of the file matching filename
    """
    try:
        files = []
        page_token = None
        while True:
            # pylint: disable=maybe-no-member
            response = (
                service.files()
                .list(
                    q=f"mimeType='{mime_type}' and name='{filename}'",
                    spaces="drive",
                    fields="nextPageToken, " "files(id, name)",
                    pageToken=page_token,
                )
                .execute()
            )
            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken", None)
            if page_token is None:
                break

    except HttpError as error:
        print(f"An error occurred: {error}")
        files = None

    return files


def create_folder(filename: str, parent: str = None) -> str:
    """
    If folder exists, returns folder id,
    else, creates and returns folder id

    Parameters
    ----------

    filename: str
        Filename

    parent: str, optional
        ID of the parent folder

    Returns
    -------
    folder_id: str
        ID of the created folder
    """

    try:
        if folder_id := search_file("application/vnd.google-apps.folder", filename):
            return folder_id[0]["id"]

    except HttpError as error:
        print(f"An error occurred: {error}")
        files = None

    try:
        # create drive api client
        if parent:
            file_metadata = {
                "name": filename,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent],
            }
        else:
            file_metadata = {
                "name": filename,
                "mimeType": "application/vnd.google-apps.folder",
            }

        # pylint: disable=maybe-no-member
        file = service.files().create(body=file_metadata, fields="id").execute()
        return file.get("id")

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def list_folder(folder_id: str) -> list:
    """
    Lists contents of Google Drive Folder

    Parameters
    ----------
    folder_id: str
        ID of the folder

    Returns
    -------
    files: list
    List of files in the folder
    """
    try:
        files = []
        page_token = None
        while True:
            # pylint: disable=maybe-no-member
            response = (
                service.files()
                .list(
                    q=f"'{folder_id}' in parents",
                    spaces="drive",
                    fields="nextPageToken, " "files(id, name, modifiedTime)",
                    pageToken=page_token,
                )
                .execute()
            )
            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken", None)
            if page_token is None:
                break

        return files

    except HttpError as error:
        print(f"An error occurred: {error}")
        files = None


def upload_file(
    path: str,
    name: str,
    parent: str = None,
    folder: bool = False,
    local_overwrite: bool = True,
    file_id: str = None,
) -> str:
    """
    Uploads file to Google Drive

    Parameters
    ----------
    path: str
        Path to the file to be uploaded

    name: str
        Name of the file to be uploaded

    parent: str, optional
        ID of the parent Google Drive folder

    folder: bool, optional
        Whether the content to be uploaded is a folder

    local_overwrite: bool, optional
        Whether to overwrite an existing file

    file_id: str, optional
        File ID if overwrite is false
    """
    if folder:
        if path[-1] == "/":
            path = path[:-1]
        zip_location = path + name + ".zip"
        if os.path.exists(zip_location):
            os.remove(zip_location)
        print("Zipping")
        if os.path.isdir(path):
            make_archive(path + name, "zip", path)
            path = zip_location
    try:
        print("Uploading")

        # Create the media upload request
        media = MediaFileUpload(path, resumable=True)

        # Perform the upload
        if overwrite or local_overwrite:
            drive_file = (
                service.files()
                .create(
                    body={
                        "name": name if ".zip" in name else f"{name}.zip",
                        "parents": [parent],
                    },
                    media_body=media,
                    fields="id",
                )
                .execute()
            )
        else:
            drive_file = (
                service.files()
                .update(
                    fileId=file_id,
                    media_body=media,
                    fields="id",
                )
                .execute()
            )

        file_id = drive_file.get("id")
        if persistent:
            revision_id = (
                service.revisions()
                .list(fileId=file_id)
                .execute()["revisions"][-1]["id"]
            )
            service.revisions().update(
                fileId=file_id,
                revisionId=revision_id,
                body={"keepForever": True},
            ).execute()
        os.remove(path)

    except HttpError as error:
        print(f"An error occurred: {error}")
        file_id = None

    return file_id


def download(file_id: str):
    try:
        # create drive api client

        # pylint: disable=maybe-no-member
        request = service.files().get_media(fileId=file_id)
        zip_file = io.BytesIO()
        downloader = MediaIoBaseDownload(zip_file, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}.")

    except HttpError as error:
        print(f"An error occurred: {error}")
        zip_file = None

    return zip_file


def delete_file(file_id):
    """
    Permanently delete a file, skipping the trash.

    Parameters
    ----------

        file_id: str
            ID of the file to delete.
    Returns
    -------
    status : bool
        Returns true if successful, false if not

    """
    try:
        service.files().delete(fileId=file_id).execute()
        return True
    except HttpError as error:
        print(f"An error occurred: {error}")
        return False


def get_revisions(file_id):
    revisions = service.revisions().list(fileId=file_id).execute()

    # Print information about each revision
    return revisions.get("revisions", [])


# endregion


# region SaveSync functions·


def load_config() -> dict:
    """
    Returns the contents of the configuration file in json format

    Returns
    -------
    save_json: dict
        Contents of the configuration file as a dict.
    """
    save_json = {"games": {}}
    if os.path.exists(list_file):
        with open(list_file, "r") as sjson:
            try:
                save_json = json.load(sjson)
            except json.decoder.JSONDecodeError:
                return save_json
    return save_json


def save_config(save_json: dict):
    """
    Saves a dictionary of configuration settings to the config file

    Parameters
    ----------
    save_json : dict
        Configuration settings in dictionary format
    """

    with open(list_file, "w") as sjson:
        json.dump(save_json, sjson, indent=4)


def pcgw_search(search_term: str, steam_id: bool = False) -> list:
    """
    Parameters
    ----------
    search_term : str
        PCGamingWiki search term
    steam_id : bool
        Whether the search term is a Steam ID. Deafaults to False

    Returns
    -------
    save_paths : list
        List of save locations by platform (Steam, Windows, Epic Games, etc.)
    """
    # Cases:
    #    If Windows and Steam and Steam Play - Use steam directory
    #    If Windows and Steam Play - Use prefix + windows dir
    #    If Wind
    if steam_id:
        search_url = "https://pcgamingwiki.com/api/appid.php?appid="
    else:
        search_url = "https://www.pcgamingwiki.com/w/index.php?search="
    search_term = search_term.replace(" ", "+")
    result = requests.get(search_url + search_term)
    search_soup = BeautifulSoup(result.content, "html.parser")
    if search_soup.find(class_="mw-search-result-heading"):
        # print(
        #    "https://www.pcgamingwiki.com"
        #    + search_soup.find(class_="mw-search-result-heading").find("a")["href"]
        # )
        search_soup = BeautifulSoup(
            requests.get(
                "https://www.pcgamingwiki.com"
                + search_soup.find(class_="mw-search-result-heading").find("a")["href"]
            ).content,
            "html.parser",
        )
    try:
        return extract_save_locations(search_soup, search_term)
    except IndexError:
        print(search_url + search_term)


# TODO Rename this here and in `pcgw_search`
def extract_save_locations(search_soup: BeautifulSoup, search_term: str) -> list:
    """
    Parameters
    ----------
    search_soup: BeatifulSoup
        BeautifulSoup object from URL

    search_term: str
        Game search term

    Returns
    -------
    save_paths: list
        List of save paths
    """
    gamedata_table = search_soup.find_all(id="table-gamedata")[1]
    platform_list = [
        "Windows",
        "Steam",
        "Steam Play",
        "Epic Games Launcher",
        "GOG.com",
        "Microsoft Store",
    ]
    tr_list = gamedata_table.find_all("tr")
    save_paths = {}
    for tr in tr_list:
        for plat in platform_list:
            if "Steam" in tr.text:
                if "Steam Play" not in tr.text:
                    save_paths["Steam"] = tr
            elif plat in tr.text:
                save_paths[plat] = tr

    user_id = os.listdir(
        os.path.join(
            os.path.expanduser("~"),
            ".steam",
            "steam",
            "userdata",
        )
    )[0]
    steam_dir = ".var/app/com.valvesoftware.Steam/.steam/steam"
    common_dir = ".var/app/com.valvesoftware.Steam/.steam/steam/steamapps/common"
    user_profile = f"drive_c/users/{os.getlogin()}"
    for plat, tr in save_paths.items():
        if not tr.find_all("span"):
            save_paths[plat] = ""
        else:
            for span in tr.find_all("span"):
                for data in span(["style", "script"]):
                    # Remove tags
                    data.decompose()
                path = "".join(span.stripped_strings)
                path = (
                    path.replace("<Steam-folder>", steam_dir)
                    .replace("%LOCALAPPDATA%", f"{user_profile}/AppData/Local/")
                    .replace("%USERPROFILE%", user_profile)
                    .replace("<path-to-game>", f"{common_dir}/{search_term}")
                    .replace("\\", "/")
                    .replace("<user-id>", user_id)
                    if path
                    else ""
                )
                if path.endswith(f"{user_id}/"):
                    path = path.replace(f"{user_id}/", "")

                path = os.path.join(*path.split("/"))
                save_paths[plat] = path
    return save_paths


def check_pcgw_location(game_title: str, platform: str, prefix_path: str) -> str:
    """
    Parameters
    ----------
    game_title : str
        Game title
    platform: str
        Epic or Steam store
    prefix_path: str
        Path to game's wineprefix

    Returns
    -------
    prefix_path : str
        Valid save path
    """
    if platform == "Epic":
        pcgw = pcgw_search(game_title)
        locations = [
            pcgw_loc[1]
            for pcgw_loc in pcgw.items()
            if pcgw_loc[0] in ["Windows", "Epic Games Launcher"]
        ]
        for loc in locations:
            if os.path.exists(os.path.join(prefix_path, loc)):
                return os.path.join(prefix_path, loc)
            if "Documents" in loc:
                short_loc = os.path.join(
                    prefix_path, loc[: loc.find("/", loc.index("Documents") + 10) + 1]
                )
                my_games_loc = os.path.join(
                    prefix_path,
                    f"{short_loc[:short_loc.index('Documents') + 10]}My Games/{short_loc[short_loc.index('Documents') + 10:]}",
                )
                if os.path.exists(short_loc):
                    return short_loc
                if os.path.exists(my_games_loc):
                    return my_games_loc
        return prefix_path
    elif platform == "Steam":
        return prefix_path


def gen_soup(url: str) -> BeautifulSoup:
    """
    Generates a BeautifulSoup for a given URL

    Parameters
    ----------
    url : str
        URL to generate a BeautifulSoup

    Returns
    -------
    BeautifulSoup : BeautifulSoup
        Soup for the given URL
    """
    result = requests.get(url)
    return BeautifulSoup(result.content, "html.parser")


def upload_game(
    folder_name: str, game: SaveDir, upload_time: datetime, root: str
) -> list:
    """
    Parameters
    ----------
    folder_name : str
        Name of the folder to upload to

    game: SaveDir
        SaveDir object for game

    upload_time : datetime
        datetime object of the upload

    root: str
    ID of Google Drive Folder

    Returns
    -------
    status: list
        List containing bool of upload success and if so, upload time.
    """
    # Find files already in Drive
    drive_folder = create_folder(folder_name, parent=root)
    files = list_folder(drive_folder)
    local_overwrite = True
    cloud_file = [
        save_file for save_file in files if save_file["name"] == f"{game.name}.zip"
    ]
    upload_time = datetime.fromtimestamp(upload_time, tz=timezone.utc)
    local_modified = datetime.fromtimestamp(game.modified, tz=timezone.utc)

    print(f"Working on {game.name}")
    # Check if cloud file was modified before or after upload time
    if cloud_file:
        date_time_obj = datetime.fromisoformat(cloud_file[0]["modifiedTime"])
        if upload_time < local_modified and upload_time != datetime.fromtimestamp(
            0, tz=timezone.utc
        ):
            print("Cloud file found, Syncing")
            if not overwrite:
                questions = [
                    inquirer.List(
                        "delete",
                        message=f"Do you want to delete the cloud file or upload as revision? (Cloud version uploaded:{date_time_obj.strftime('%b %-d %Y, %H:%M:%S')})",
                        choices=["Delete", "Update"],
                    )
                ]
                answer = inquirer.prompt(questions, theme=GreenPassion())
            if overwrite or answer["delete"] == "Delete":
                delete_status = delete_file(cloud_file[0]["id"])
                if not delete_status:
                    print("Deletion Failed")
                    return [False, None]
                local_overwrite = True
            else:
                local_overwrite = False

        elif date_time_obj < upload_time:
            print(f"Skipping {game.name}, Google Drive up to date")
            return [False, None]
        elif date_time_obj > upload_time or upload_time == datetime.fromtimestamp(
            0, tz=timezone.utc
        ):
            choices = [
                f"Replace with cloud version (Uploaded: {date_time_obj.strftime('%b %-d %Y, %H:%M:%S')})",
                f"Upload current version (Modified: {local_modified.strftime('%b %-d %Y, %H:%M:%S')})",
                "Skip",
            ]
            questions = [
                inquirer.List(
                    "cloud",
                    message="Cloud file is more recent, what would you like to do?",
                    choices=choices,
                )
            ]
            answer = inquirer.prompt(questions, theme=GreenPassion())
            if answer["cloud"] == choices[0]:
                print("Syncing")
                fetch_cloud_file(game, cloud_file[0]["id"])
                print("Completed!")
                return [True, float(date_time_obj.strftime("%s"))]
            elif answer["cloud"] == choices[2]:
                print("Sync cancelled")
                return [False, None]
            elif answer["cloud"] == choices[1]:
                local_overwrite = False
                """consent = input("Cloud file is more recent, sync with cloud? (Y/n)")
                if consent.lower() == "y":
                    print("Syncing")
                    fetch_cloud_file(game, cloud_file[0]["id"])
                    print("Completed!")
                else:
                    print("Sync cancelled")"""
    file_id = upload_file(
        game.path,
        f"{game.name}.zip",
        drive_folder,
        True,
        local_overwrite,
        None if local_overwrite else cloud_file[0]["id"],
    )
    print(f"Finished {game.name}")
    return [True, float(datetime.now().strftime("%s"))]


def add_custom(game_name, path):
    config = load_config()
    if os.path.exists(path):
        config["games"][game_name] = {"path": os.path.abspath(path), "uploaded": 0}
    save_config(config)


def steam_sync(root: str):
    """
    stub
    """
    config = configparser.ConfigParser()
    config.read(os.path.join(config_dir, "config.ini"))
    steam_dir = ""
    if config["Steam"]["package_manager"] == "Distro":
        steam_dir = os.path.join(os.path.expanduser("~"), ".steam")
    elif config["Steam"]["package_manager"] == "Flatpak":
        steam_dir = os.path.join(
            os.path.expanduser("~"), ".var", "app", "com.valvesoftware.Steam", ".steam"
        )

    pcgw_api_url = "https://pcgamingwiki.com/api/appid.php?appid="
    steam_games = []
    for game_title in os.listdir(
        os.path.join(steam_dir, "steam", "steamapps", "common")
    ):
        pcgw_search(game_title)

    for steam_game in steam_games:
        print(steam_game)


def heroic_sync(root: str):  # sourcery skip: extract-method
    """
    Sync Heroic files

    Parameters
    ----------

    root: str
        ID of SaveHaven folder in Google Drive
    """

    heroic_saves = []
    if os.path.exists(list_file):
        save_json = load_config()
        prefixes = os.listdir(heroic_dir)
        missing_games = [
            game for game in prefixes if game not in save_json["games"].keys()
        ]
        for key, value in save_json["games"].items():
            if os.path.exists(value["path"]):
                save_path = value["path"]
                modified_time = os.path.getmtime(save_path)
            elif os.path.exists(os.path.join(heroic_dir, key)):
                save_path = check_pcgw_location(
                    key, "Epic", os.path.join(heroic_dir, key)
                )
                modified_time = os.path.getmtime(save_path)
            else:
                save_path = "N/A"
                modified_time = 0
            heroic_saves.append(SaveDir(key, save_path, modified_time))
        if missing_games:
            print("Processing files and making API calls...")
        for files in tqdm(
            missing_games,
            bar_format="{desc}: {n_fmt}/{total_fmt}|{bar}|",
            desc="Progress",
            leave=False,
            ncols=50,
            unit="file",
        ):
            prefix_path = os.path.join(heroic_dir, files)
            # selected_game.path = check_pcgw_location(selected_game.name, "Epic", selected_game.path)
            save_path = check_pcgw_location(files, "Epic", prefix_path)
            heroic_saves.append(
                SaveDir(
                    files,
                    save_path,
                    os.path.getmtime(save_path),
                )
            )
    else:
        save_json = {"games": {}, "minecraft": {}}
        print("Processing files and making API calls...")
        for files in tqdm(
            os.listdir(heroic_dir),
            bar_format="{desc}: {n_fmt}/{total_fmt}|{bar}|",
            desc="Progress",
            leave=False,
            ncols=50,
            unit="file",
        ):
            if os.path.isdir(os.path.join(heroic_dir, files)):
                prefix_path = os.path.join(heroic_dir, files)
                # selected_game.path = check_pcgw_location(selected_game.name, "Epic", selected_game.path)
                save_path = check_pcgw_location(files, "Epic", prefix_path)
                heroic_saves.append(
                    SaveDir(
                        files,
                        save_path,
                        os.path.getmtime(save_path),
                    )
                )
    for save in heroic_saves:
        if len(save_json["games"]) > 0 and save.name in save_json["games"].keys():
            continue
        save_json["games"][save.name] = {"path": save.path, "uploaded": 0}

    questions = [
        inquirer.Checkbox(
            "selected_games",
            message="Select games to backup",
            choices=[i.name for i in heroic_saves],
        )
    ]

    choices = [i.name for i in heroic_saves]
    answers = fzf.prompt(choices, "--multi --cycle")

    print("Backing up these games: ")

    selected_games = []
    for i in answers:
        print(f"    {i}")
        selected_games.extend(j for j in heroic_saves if j.name == i)

    for game in selected_games:
        if game.path != "N/A":
            upload_status = upload_game(
                "Heroic", game, save_json["games"][game.name]["uploaded"], root
            )
            if upload_status[0] == True:
                save_json["games"][game.name]["uploaded"] = upload_status[1]
    save_config(save_json)


def minecraft_sync(root: str):
    """
    Sync Minecraft files

    Parameters
    ----------

    root: str
        ID of SaveHaven folder in Google Drive
    """
    print("Minceraft")
    config = configparser.ConfigParser()
    config.read(os.path.join(config_dir, "config.ini"))
    save_json = load_config()
    if "minecraft" not in save_json.keys():
        save_json["minecraft"] = {}
    worlds = {
        launcher: get_worlds(launcher)
        for launcher in config["Minecraft"]["selected"].split(",")
    }
    for launcher, launcher_worlds in worlds.items():
        if launcher not in save_json["minecraft"].keys():
            save_json["minecraft"][launcher] = {}
        for world in launcher_worlds:
            print(f"Backing up {world.name}")
            if world.name not in save_json["minecraft"][launcher].keys():
                save_json["minecraft"][launcher][world.name] = {
                    "path": world.path,
                    "uploaded": 0,
                }
            minecraft_folder = create_folder("Minecraft", parent=root)
            upload_status = upload_game(
                launcher,
                world,
                save_json["minecraft"][launcher][world.name]["uploaded"],
                minecraft_folder,
            )
            if upload_status[0] == True:
                save_json["minecraft"][launcher][world.name]["uploaded"] = (
                    upload_status[1]
                )
    save_config(save_json)


def get_worlds(launcher: str):
    """
    Parameters
    ----------
    launcher : str
        Minecraft Launcher (MultiMC, PrismLauncher, Official)

    Returns
    -------
    worlds : list
        list of SaveDir objects of Minecraft worlds
    """
    locations = {
        "Official": os.path.join(os.path.expanduser("~"), ".minecraft"),
        "Prism Launcher": os.path.join(
            os.path.expanduser("~"),
            ".local",
            "share",
            "PrismLauncher",
            "instances",
        ),
        "MultiMC": os.path.join(
            os.path.expanduser("~"),
            ".local",
            "share",
            "MultiMC",
            "instances",
        ),
    }
    worlds = []
    if launcher in {"Prism Launcher", "MultiMC"}:
        instances = [
            x
            for x in os.listdir(locations[launcher])
            if x not in [".LAUNCHER_TEMP", "instgroups.json"]
            and os.path.isdir(locations[launcher])
        ]
        questions = [
            inquirer.Checkbox(
                "selected_instances",
                message=f"Select instances from {launcher}",
                choices=instances,
            )
        ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
        for instance in answers["selected_instances"]:
            saves_dir = os.path.join(
                locations[launcher],
                instance,
                ".minecraft" if launcher == "Prism Launcher" else "minecraft",
                "saves",
            )
            instance_worlds = os.listdir(saves_dir)
            questions = [
                inquirer.Checkbox(
                    "selected_worlds",
                    message=f"Select worlds from {instance}",
                    choices=instance_worlds,
                )
            ]
            answers = inquirer.prompt(questions, theme=GreenPassion())
            worlds = [
                SaveDir(
                    world,
                    os.path.join(saves_dir, world),
                    os.path.getmtime(os.path.join(saves_dir, world)),
                )
                for world in answers["selected_worlds"]
            ]
    else:
        instance_worlds = os.listdir(os.path.join(locations[launcher], "saves"))
        questions = [
            inquirer.Checkbox(
                "selected_worlds",
                message="Select worlds",
                choices=instance_worlds,
            )
        ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
        worlds = [
            SaveDir(
                x,
                os.path.join(os.path.join(locations[launcher], "saves", x)),
                os.path.getmtime(os.path.join(locations[launcher], "saves", x)),
            )
            for x in answers["selected_worlds"]
        ]
    return worlds


def search_dir(root: str):
    """
    Scan directories for save files

    Parameters
    ----------
    root: str
        ID of the SaveHaven folder on Drive
    """
    # TODO: Make this shit readable
    # Gets selected launchers
    config = configparser.ConfigParser()
    config.read(os.path.join(config_dir, "config.ini"))
    launchers = config["Launchers"]["selected"].split(",")
    home_path = os.path.expanduser("~")

    # Heroic scanning
    if "Games" in os.listdir(home_path) and "Heroic" in launchers:
        heroic_sync(root)

    if "Minecraft" in launchers:
        minecraft_sync(root)
    """
    if "Steam" in launchers:
        steam_sync(root)
    """


def backup(p: bool = False, o: bool = False):
    """
    Performs a backup of save files to the SaveHaven cloud storage.

    Args:
        p (bool, optional): Flag indicating whether to enable persistent storage. Defaults to False.
        o (bool, optional): Flag indicating whether to enable overwrite mode. Defaults to False.

    Returns:
        None

    Examples:
        backup(p=True, o=False)
    """

    # TODO: add support for persistent (store this version of the file permanently) and overwrite (delete previous file in Google Drive instead of prompting for deletion or updating)
    global persistent
    persistent = p
    global overwrite
    overwrite = o
    config = os.path.join(config_dir, "config.ini")
    if not os.path.exists(config):
        print("Config file not found, running intialization")
        print("Select launchers (if not listed, add paths manually):")
        update_launchers()

    # If SaveHaven folder doesn't exist, create it.
    folder = create_folder(filename="SaveHaven")

    # Search for save file directories
    search_dir(folder)


def list_cloud():
    """
    Lists the revisions of files in the SaveHaven cloud storage.

    Args:
        None

    Returns:
        None

    Examples:
        list_cloud()
    """

    folder = create_folder(filename="SaveHaven")
    savehaven_folder = list_folder(folder)
    questions = [
        inquirer.List(
            "folders",
            message="Select folders to list",
            choices=[x["name"] for x in savehaven_folder],
        )
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_folder = list_folder(
        [x["id"] for x in savehaven_folder if x["name"] == answers["folders"]][0]
    )
    options = [x["name"] for x in selected_folder]
    questions = [
        inquirer.List(
            "files",
            message="Select revisions to list",
            choices=options,
        )
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_file = [x for x in selected_folder if x["name"] == answers["files"]]
    revisions = get_revisions(selected_file[0]["id"])
    options = [
        f"Version {x + 1} {revisions[x]['modifiedTime']}" for x in range(len(revisions))
    ]
    questions = [
        inquirer.Checkbox(
            "revision",
            message="Select revisions to list",
            choices=options,
        )
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    for revision in answers["revision"]:
        service.revisions().update(
            fileId=selected_file[0]["id"],
            revisionId=[
                x["id"]
                for x in revisions
                if revision[revision.rfind(" ") + 1 :] == x["modifiedTime"]
            ][0],
            body={"keepForever": True},
        ).execute()


def get_save_location(name: str) -> str:
    """
    Gets the save location for a game by searching the Steam store.

    Args:
        name (str): The name of the game.

    Returns:
        str: The save location of the game.

    Examples:
        save_location = get_save_location(name)
    """

    steam_search_url = "https://store.steampowered.com/search/?term="
    search_term = name.replace(" ", "+")
    steam_search = requests.get(steam_search_url + search_term)
    search_soup = BeautifulSoup(steam_search.content, "html.parser")
    result = search_soup.find("a", class_="search_result_row")
    game_id = result["href"].replace("https://store.steampowered.com/app/", "")
    game_id = game_id[: game_id.index("/")]


def update_launchers():
    """
    Update config file with launchers

    Parameters
    ----------
    launchers: list
        List of launchers

    """
    questions = [
        inquirer.Checkbox(
            "launchers",
            message="Select launchers (space to select, enter to confirm)",
            choices=["Steam", "Heroic", "Legendary", "GOG Galaxy", "Minecraft"],
        ),
        inquirer.Confirm(
            "steam",
            message="Steam has its own cloud sync, are you sure?",
            ignore=lambda x: "Steam" not in x["launchers"],
        ),
        inquirer.List(
            "steam_package_manager",
            message="Steam has its own cloud sync, are you sure?",
            choices=["Distro (apt, pacman, dnf)", "Flatpak", "Snap"],
            ignore=lambda x: "Steam" not in x["launchers"] or not x["steam"],
        ),
        inquirer.Checkbox(
            "mclaunchers",
            message="Select Minecraft launchers (space to select, enter to confirm)",
            choices=["Official", "Prism Launcher", "MultiMC"],
            ignore=lambda x: "Minecraft" not in x["launchers"],
        ),
    ]

    answers = inquirer.prompt(questions, theme=GreenPassion())
    config = configparser.ConfigParser()
    config["Launchers"] = {"selected": ",".join(answers["launchers"])}
    if answers["steam"] and answers["steam_package_manager"]:
        config["Steam"] = {"selected": answers["steam_package_manager"]}
    if answers["mclaunchers"]:
        config["Minecraft"] = {"selected": ",".join(answers["mclaunchers"])}
    with open(os.path.join(config_dir, "config.ini"), "w") as list_file:
        config.write(list_file)


def fetch_cloud_file(game: SaveDir, cloud_file: str):
    """
    Fetches a file from the cloud and restores it to the specified game directory.

    Args:
        game (SaveDir): The game directory to restore the file to.
        cloud_file (str): The ID of the file in the cloud.

    Returns:
        None

    Examples:
        fetch_cloud_file(game, cloud_file)
    """

    game_backup = os.path.join(
        backups_dir, game.name, datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    )
    if not os.path.exists(os.path.join(backups_dir, game.name)):
        os.mkdir(os.path.join(backups_dir, game.name))
    move(game.path, game_backup)
    zip_file = download(cloud_file)
    with open(os.path.join(tmp_dir, f"{game.name}.zip"), "wb") as downloaded_file:
        downloaded_file.write(zip_file.getbuffer())
    unpack_archive(
        os.path.join(tmp_dir, f"{game.name}.zip"),
        os.path.join(tmp_dir, game.name),
    )
    os.remove(os.path.join(tmp_dir, f"{game.name}.zip"))
    os.mkdir(game.path)
    for file in os.listdir(os.path.join(tmp_dir, game.name)):
        move(
            os.path.join(tmp_dir, game.name, file),
            game.path,
        )


def restore():
    """
    Restores files from the SaveHaven backup.

    Args:
        None

    Returns:
        None

    Examples:
        restore()
    """

    root_folder = create_folder(filename="SaveHaven")
    config = load_config()
    folders = list_folder(root_folder)
    if len(folders) > 1:
        questions = [
            inquirer.Checkbox(
                "folder",
                message="Choose folders.",
                choices=[x["name"] for x in folders],
            )
        ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
        folders = [x for x in folders if x["name"] in answers["folder"]]
    for folder in folders:
        files = list_folder(create_folder(filename=folder["name"], parent=root_folder))
        local_files = [
            (
                SaveDir(key, value["path"], os.path.getmtime(value["path"]))
                if os.path.exists(value["path"])
                else SaveDir(key, "N/A", "N/A")
            )
            for key, value in config["games"].items()
        ]
        cloud_files = []
        filenames = [x.name for x in local_files]
        # for i in range(len(files)):
        i = 0
        while i < len(files):
            cloud_files.append(f"{files[i]['name'][:-4]} (Uploaded:)")
            if cloud_files[i][:-12] not in filenames:
                files.pop(i)
            else:
                i += 1
    questions = [
        inquirer.Checkbox("files", message="Select files to restore", choices=files)
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    for answer in answers["files"]:
        name = answer["name"][:-4]
        for save in local_files:
            if name == save.name:
                fetch_cloud_file(save, answer["id"])


# endregion

if __name__ == "__main__":
    restore()
