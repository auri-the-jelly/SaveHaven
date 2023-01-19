# region Imports
import os
import io
import json
import sqlite3
import requests
import configparser

from datetime import datetime
from appdirs import user_config_dir
from bs4 import BeautifulSoup
from shutil import make_archive, unpack_archive

import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]
from savehaven.configs import creds

config_dir = user_config_dir("SaveHaven", "Aurelia")
if not os.path.exists(config_dir):
    os.mkdir(config_dir)


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
def mod_time(file_id: str) -> datetime:
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
        # create drive api client
        service = build("drive", "v3", credentials=creds)

        file = service.files().get(fileId=file_id, fields="modifiedTime").execute()
        modified_time = file["modifiedTime"]
        date_time_obj = datetime.strptime(modified_time, "%Y-%m-%dT%H:%M:%S.%fZ")
        return date_time_obj

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
        service = build("drive", "v3", credentials=creds)
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
        # create drive api client
        folder_id = search_file("application/vnd.google-apps.folder", filename)

        if folder_id:
            return folder_id[0]["id"]

    except HttpError as error:
        print(f"An error occurred: {error}")
        files = None

    try:
        # create drive api client
        service = build("drive", "v3", credentials=creds)
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
        service = build("drive", "v3", credentials=creds)
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


def upload_file(path: str, name: str, parent: str = None, folder: bool = False) -> str:
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
    """
    if folder:
        zip_location = path + ".zip"
        if os.path.exists(zip_location):
            os.remove(zip_location)
        print("Zipping")
        make_archive(path, "zip", path)
        path = zip_location
    file_id = None
    try:
        service = build("drive", "v3", credentials=creds)

        print("Uploading")

        # Create the media upload request
        media = MediaFileUpload(path, resumable=True)

        # Perform the upload
        file = (
            service.files()
            .create(
                body={"name": name, "parents": [parent]}, media_body=media, fields="id"
            )
            .execute()
        )

        file_id = file.get("id")
        os.remove(zip_location)

    except HttpError as error:
        print(f"An error occurred: {error}")
        file_id = None

    return file_id


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
        service = build("drive", "v3", credentials=creds)

        service.files().delete(fileId=file_id).execute()
        return True
    except HttpError as error:
        print(f"An error occurred: {error}")
        return False


# endregion

# region SaveSync functions


def gen_soup(url: str):
    result = requests.get(url)
    result_soup = BeautifulSoup(result.content, "html.parser")
    return result_soup

def steam_sync(root: str):
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
    for appid in os.listdir(
        os.path.join(steam_dir, "steam", "steamapps", "compatdata")
    ):
        game_path = os.path.join(steam_dir, "steam", "steamapps", "compatdata", appid)
        pcgw_url = pcgw_api_url + appid
        print(pcgw_url)
        pcgw_soup = gen_soup(pcgw_url)
        if not pcgw_soup.find(string="No such AppID."):
            for game_title in pcgw_soup.find_all(class_="article-title"):
                print(game_title.text)
                steam_games.append(SaveDir(game_title.text, game_path, os.path.getmtime(os.path.join(steam_dir, "steam", "steamapps", "compatdata", appid))))
        
    for steam_game in steam_games:
        print(steam_game)


def heroic_sync(root: str):
    """
    Sync Heroic files

    Parameters
    ----------
    save_dirs: list
        List of SaveDir objects of games in Heroic directories

    root: str
        ID of SaveHaven folder in Google Drive
    """
    # Save JSON
    home_path = os.path.expanduser("~")
    games_dir = os.path.join(home_path, "Games")
    heroic_dir = os.path.join(games_dir, "Heroic", "Prefixes")
    heroic_saves = []
    # Add prefixes to list
    for file in os.listdir(heroic_dir):
        if os.path.isdir(os.path.join(heroic_dir, file)):
            save_path = os.path.join(heroic_dir, file)
            heroic_saves.append(SaveDir(file, save_path, os.path.getmtime(save_path)))

    # Read config for added games
    print("Found Heroic game saves:")
    save_json = {"games": {}}
    if os.path.exists(os.path.join(config_dir, "config.json")):
        config_file = open(os.path.join(config_dir, "config.json"))
        save_json = json.load(config_file)
        config_file.close()
    saves_dict = {"games": {}}

    # Add games to config
    for i in range(len(heroic_saves)):
        if save_json["games"] and not heroic_saves[i].name in save_json["games"].keys():
            save_json["games"][heroic_saves[i].name] = {
                "path": heroic_saves[i].path,
                "uploaded": 0,
            }
        else:
            saves_dict["games"][heroic_saves[i].name] = {
                "path": heroic_saves[i].path,
                "uploaded": 0,
            }
        print(f"{i+1}. {heroic_saves[i].name}")
    if not os.path.exists(os.path.join(config_dir, "config.json")):
        with open(os.path.join(config_dir, "config.json"), "w") as sjson:
            json.dump(saves_dict, sjson, indent=4)
    else:
        with open(os.path.join(config_dir, "config.json"), "w") as sjson:
            json.dump(save_json, sjson, indent=4)

    # Selecting games to sync
    while True:
        sync_nums = input(
            "Enter range (3-5) or indexes (1,3,5), q to quit and empty for all: "
        )
        valid_chars = "1234567890-,"
        valid = True
        if "q" in sync_nums:
            quit()
        elif "s" in sync_nums:
            return
        for i in sync_nums:
            if i not in valid_chars:
                print("Invalid characters")
                valid = False
                break
            if i.isnumeric() and int(i) > len(heroic_saves):
                print("Index out of range")
                valid = False
                break
        if valid == False:
            continue
        if sync_nums.count("-") > 1 or ("-" in sync_nums and "," in sync_nums):
            print("Specify no more than range, or use list")
            continue
        try:
            if "-" in sync_nums:
                indices = list(
                    range(
                        int(sync_nums.split("-")[0]), int(sync_nums.split("-")[1]) + 1
                    )
                )

            elif "," in sync_nums:
                indices = sync_nums.split(",")

            elif len(sync_nums) == 1:
                indices = [int(sync_nums)]

            elif sync_nums == "":
                indices = list(range(1, len(heroic_saves) + 1))

            print("Backing up these games: ")
            for i in range(len(indices)):
                indices[i] = int(indices[i]) - 1
                print(heroic_saves[indices[i]])
            break
        except Exception as e:
            print("Error occured: ", e)

    selected_games = [heroic_saves[index] for index in indices]
    saves_file = open(os.path.join(config_dir, "config.json"), "r")
    save_json = json.load(saves_file)
    saves_file.close()
    for selected_game in selected_games:
        # Find files already in Drive
        heroic_folder = create_folder("Heroic", parent=root)
        files = list_folder(heroic_folder)
        cloud_file = [
            file for file in files if file["name"] == selected_game.name + ".zip"
        ]

        print(f"Working on {selected_game.name}")
        # Check if cloud file was modified before or after upload time
        if len(cloud_file) > 0:
            date_time_obj = datetime.strptime(
                cloud_file[0]["modifiedTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).strftime("%s")
            print(
                f"{float(date_time_obj)} {float(selected_game.modified)} {save_json['games'][selected_game.name]['uploaded']}"
            )
            if float(save_json["games"][selected_game.name]["uploaded"]) < float(
                selected_game.modified
            ):
                print("Cloud file found, Syncing")
                delete = delete_file(cloud_file[0]["id"])
                if not delete:
                    print("Deletion Failed")
                    continue
            elif float(date_time_obj) < float(
                save_json["games"][selected_game.name]["uploaded"]
            ):
                print(f"Skipping {selected_game.name}, Google Drive up to date")
                continue
            elif float(date_time_obj) > float(
                save_json["games"][selected_game.name]["uploaded"]
            ):
                consent = input("Cloud file is more recent, sync with cloud? (Y/n)")
                if consent.lower() == "y":
                    print("Syncing")
                    download(cloud_file[0]["id"])
                    continue
                else:
                    print("Sync cancelled")
        """if os.path.exists(zip_location):
            os.remove(zip_location)
        print("Zipping")
        make_archive(selected_game.path, 'zip', selected_game.path)
        print("Uploading")"""
        file_id = upload_file(
            selected_game.path, selected_game.name + ".zip", heroic_folder, True
        )
        save_json["games"][selected_game.name]["uploaded"] = float(
            datetime.now().strftime("%s")
        )
        print(f"Finished {selected_game.name}")
    with open(os.path.join(config_dir, "config.json"), "w") as saves_file:
        json.dump(save_json, saves_file)


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
    print(config["Launchers"]["selected"])
    launchers = config["Launchers"]["selected"].split(",")
    home_path = os.path.expanduser("~")

    # Heroic scanning
    if "Games" in os.listdir(home_path) and "Heroic" in launchers:
        heroic_sync(root)

    if "Steam" in launchers:
        steam_sync(root)

def sync():
    config = os.path.join(config_dir, "config.ini")
    if not os.path.exists(config):
        print("Config file not found, running intialization")
        print("Select launchers (if not listed, add paths manually):")
        update_launchers()

    # If SaveHaven folder doesn't exist, create it.
    folder = create_folder(filename="SaveHaven")
    print("Created " + folder)

    # Search for save file directories
    search_dir(folder)

def download(file_id: str):
    try:
        # create drive api client
        service = build("drive", "v3", credentials=creds)

        # pylint: disable=maybe-no-member
        request = service.files().get_media(fileId=file_id)
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}.")

    except HttpError as error:
        print(f"An error occurred: {error}")
        file = None

    pass

def get_save_location(name: str) -> str:
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
    launchers = ["Steam", "Heroic", "Legendary", "GOG Galaxy"]
    for i in range(len(launchers)):
        print(f"{i + 1}. {launchers[i]}")

    while True:
        launcher_nums = input(
            "Enter range (3-5) or indexes (1,3,5), q to quit and empty for all: "
        )
        valid_chars = "1234567890-,"
        valid = True
        if "q" in launcher_nums:
            quit()
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
        if launcher_nums.count("-") > 1 or (
            "-" in launcher_nums and "," in launcher_nums
        ):
            print("Specify no more than range, or use list")
            continue
        try:
            if "-" in launcher_nums:
                indices = list(
                    range(
                        int(launcher_nums.split("-")[0]),
                        int(launcher_nums.split("-")[1]) + 1,
                    )
                )

            elif "," in launcher_nums:
                indices = launcher_nums.split(",")

            elif len(launcher_nums) == 1:
                indices = [int(launcher_nums)]

            elif launcher_nums == "":
                indices = list(range(1, len(launchers) + 1))

            print("Selecting these launchers: ")
            for i in range(len(indices)):
                indices[i] = int(indices[i]) - 1
            selected_launchers = [x for x in launchers if launchers.index(x) in indices]
            print(selected_launchers)
            break
        except Exception as e:
            print("Error occured: ", e)
    config = configparser.ConfigParser()
    config["Launchers"] = {"selected": ""}
    if "Steam" in selected_launchers:
        steam_agree = input(
            "Steam has it's own save sync, are you sure you want to backup with SaveHaven? (y/n): "
        )
        if not "y" in steam_agree:
            selected_launchers.pop(selected_launchers.index("Steam"))
        else:
            print("Select steam install type:")
            package_managers = ["Distro", "Flatpak", "Snap (needs testing)"]
            for i in range(3):
                print(f"{i + 1}. {package_managers[i]}")
            selected = input("Enter index: ")
            if selected.isnumeric() and int(selected) > 0 and int(selected) < 4:
                selected = int(selected)
                print(f"Selecting: {package_managers[selected - 1]}")

            config = configparser.ConfigParser()
            config.read(os.path.join(config_dir, "config.ini"))
            print(config.sections())
            config["Steam"] = {"Package_Manager": package_managers[selected - 1]}
            print(config.sections())
            with open(os.path.join(config_dir, "config.ini"), "w") as config_file:
                config.write(config_file)

    config["Launchers"]["selected"] = ",".join(selected_launchers)

    with open(os.path.join(config_dir, "config.ini"), "w") as config_file:
        config.write(config_file)

# endregion
