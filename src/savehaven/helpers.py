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

from savehaven.configs import creds


# endregion

# region Variables
SCOPES = ["https://www.googleapis.com/auth/drive"]
config_dir = user_config_dir("SaveHaven", "Aurelia")
if not os.path.exists(config_dir):
    os.mkdir(config_dir)
config_file = os.path.join(config_dir, "config.json")
home_path = os.path.expanduser("~")
games_dir = os.path.join(home_path, "Games")
heroic_dir = os.path.join(games_dir, "Heroic", "Prefixes")
heroic_saves = []
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
        # create drive api client
        service = build("drive", "v3", credentials=creds)

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
        if folder_id := search_file("application/vnd.google-apps.folder", filename):
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
        if path[-1] == "/":
            path = path[:-1]
        zip_location = path + name + ".zip"
        if os.path.exists(zip_location):
            os.remove(zip_location)
        print("Zipping")
        make_archive(path + name, "zip", path)
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
                body={
                    "name": name if ".zip" in name else f"{name}.zip",
                    "parents": [parent],
                },
                media_body=media,
                fields="id",
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


def load_config():
    """
    Returns the contents of the configuration file in json format

    Returns
    -------
    save_json: dict
        Contents of the configuration file as a dict.
    """
    save_json = {"games": {}}
    if os.path.exists(config_file):
        with open(config_file, "r") as sjson:
            try:
                save_json = json.load(sjson)
            except json.decoder.JSONDecodeError:
                return save_json
    return save_json


def save_config(save_json):
    """
    Saves a dictionary of configuration settings to the config file

    Parameters
    ----------
    save_json : dict
        Configuration settings in dictionary format
    """
    with open(config_file, "w") as sjson:
        json.dump(save_json, sjson, indent=4)


def pcgw_search(search_term: str, steam_id: bool = False) -> list:
    """
    Parameters
    ----------
    search_term : str
        PCGamingWiki search term
    steam_id : bool
        Whether the search term is a Steam ID

    Returns
    -------
    _extracted_from_pcgw_search_28 : list
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
        return _extracted_from_pcgw_search_28(search_soup, search_term)
    except IndexError:
        print(search_url + search_term)


# TODO Rename this here and in `pcgw_search`
def _extracted_from_pcgw_search_28(search_soup, search_term):
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
    user_profile = "drive_c/users/auri"
    for plat, tr in save_paths.items():
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


def check_pcgw_location(game_title: str, platform: str, prefix_path: str):
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


def gen_soup(url: str):
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


def steam_sync(root: str):
    """ """
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
    # Add prefixes to list
    for files in os.listdir(heroic_dir):
        if os.path.isdir(os.path.join(heroic_dir, files)):
            save_path = os.path.join(heroic_dir, files)
            heroic_saves.append(SaveDir(files, save_path, os.path.getmtime(save_path)))

    # Read config for added games
    print("Found Heroic game saves:")
    save_json = load_config()
    save_dict = {"games": {}}

    # Add games to config
    for i in range(len(heroic_saves)):
        if (
            save_json["games"].keys()
            and heroic_saves[i].name not in save_json["games"].keys()
        ):
            save_json["games"][heroic_saves[i].name] = {
                "path": heroic_saves[i].path,
                "uploaded": 0,
            }
        else:
            save_dict["games"][heroic_saves[i].name] = {
                "path": heroic_saves[i].path,
                "uploaded": 0,
            }
        print(f"{i+1}. {heroic_saves[i].name}")
    if not os.path.exists(config_file) or not save_json["games"].keys():
        save_config(save_dict)
    else:
        save_config(save_json)

    save_json = load_config()

    # Selecting games to sync
    indices = selector(
        "Enter range (3-5) or indexes (1,3,5), q to quit and empty for all: ",
        None,
        "1234567890-,",
        len(heroic_saves),
        True,
    )
    if indices[0] == "skip":
        return
    print("Backing up these games: ")
    for i in range(len(indices)):
        print(heroic_saves[indices[i]])

    selected_games = [heroic_saves[index] for index in indices]

    for selected_game in selected_games:
        # Find files already in Drive
        heroic_folder = create_folder("Heroic", parent=root)
        files = list_folder(heroic_folder)
        cloud_file = [
            save_file
            for save_file in files
            if save_file["name"] == f"{selected_game.name}.zip"
        ]

        print(f"Working on {selected_game.name}")
        # Check if cloud file was modified before or after upload time
        if cloud_file:
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
        selected_game.path = check_pcgw_location(
            selected_game.name, "Epic", selected_game.path
        )
        file_id = upload_file(
            selected_game.path, f"{selected_game.name}.zip", heroic_folder, True
        )

        save_json["games"][selected_game.name]["uploaded"] = float(
            datetime.now().strftime("%s")
        )
        print(f"Finished {selected_game.name}")
    with open(os.path.join(config_dir, "config.json"), "w") as saves_file:
        json.dump(save_json, saves_file)


def minecraft_sync(root: str):
    mc_launchers = ["Official Launcher", "Prism Launcher", "MultiMC"]
    indices = selector(
        "Choose launcher:", mc_launchers, "1234567890-,", len(mc_launchers), False
    )
    for i in indices:
        print(mc_launchers[indices[i]])


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

    if "Minecraft" in launchers:
        minecraft_sync(root)
    """
    if "Steam" in launchers:
        steam_sync(root)
    """


def sync():
    config = os.path.join(config_dir, "config.ini")
    if not os.path.exists(config):
        print("Config file not found, running intialization")
        print("Select launchers (if not listed, add paths manually):")
        update_launchers()

    # If SaveHaven folder doesn't exist, create it.
    folder = create_folder(filename="SaveHaven")
    print(f"Created {folder}")

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
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}.")

    except HttpError as error:
        print(f"An error occurred: {error}")
        file = None


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
    launchers = ["Steam", "Heroic", "Legendary", "GOG Galaxy", "Minecraft"]
    indices = selector(
        "Enter range (3-5) or indexes (1,3,5), q to quit and empty for all:",
        launchers,
        "1234567890-,",
        len(launchers),
        True,
    )
    print("Selecting these launchers:")
    for i in indices:
        print(launchers[i])
    selected_launchers = [
        launcher for launcher in launchers if launchers.index(launcher) in indices
    ]
    config = configparser.ConfigParser()
    config["Launchers"] = {"selected": ""}
    if "Steam" in selected_launchers:
        steam_agree = input(
            "Steam has it's own save sync, are you sure you want to backup with SaveHaven? (y/n): "
        )
        if "y" not in steam_agree:
            selected_launchers.pop(selected_launchers.index("Steam"))
        else:
            config = _extracted_from_update_launchers_74()
    config["Launchers"]["selected"] = ",".join(selected_launchers)

    with open(os.path.join(config_dir, "config.ini"), "w") as config_file:
        config.write(config_file)
    """
    for i in range(len(launchers)):
        print(f"{i + 1}. {launchers[i]}")

    valid_chars = "1234567890-,"
    while True:
        launcher_nums = input(
            "Enter range (3-5) or indexes (1,3,5), q to quit and empty for all: "
        )
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
        if "y" not in steam_agree:
            selected_launchers.pop(selected_launchers.index("Steam"))
        else:
            config = _extracted_from_update_launchers_74()
    config["Launchers"]["selected"] = ",".join(selected_launchers)

    with open(os.path.join(config_dir, "config.ini"), "w") as config_file:
        config.write(config_file)"""


# TODO Rename this here and in `update_launchers`
def _extracted_from_update_launchers_74():
    print("Select steam install type:")
    package_managers = ["Distro", "Flatpak", "Snap (needs testing)"]
    for i in range(3):
        print(f"{i + 1}. {package_managers[i]}")
    selected = input("Enter index: ")
    if selected.isnumeric() and int(selected) > 0 and int(selected) < 4:
        selected = int(selected)
        print(f"Selecting: {package_managers[selected - 1]}")
    else:
        print("Invalid input try again")
        quit()

    result = configparser.ConfigParser()
    result.read(os.path.join(config_dir, "config.ini"))
    print(result.sections())
    result["Steam"] = {"Package_Manager": package_managers[selected - 1]}
    print(result.sections())
    with open(os.path.join(config_dir, "config.ini"), "w") as config_file:
        result.write(config_file)

    return result


def selector(
    message: str, item_list: list, valid_chars: str, length: int, multi_input: bool
) -> list:
    if item_list:
        for i in range(len(item_list)):
            print(f"{i + 1}. {item_list[i]}")

    while True:
        nums = input(message)
        valid = True
        if "q" in nums:
            quit()
        elif "s" in nums:
            return ["skip"]
        for i in nums:
            if i not in valid_chars:
                print("Invalid characters")
                valid = False
                break
            if i.isnumeric() and int(i) > (len(item_list) if item_list else length):
                print("Index out of range")
                valid = False
                break
        if valid == False:
            continue
        if nums.count("-") > 1 or ("-" in nums and "," in nums):
            print("Specify no more than one range, or use list")
            continue
        try:
            if multi_input:
                if "-" in nums:
                    indices = list(
                        range(int(nums.split("-")[0]), int(nums.split("-")[1]) + 1)
                    )

                elif "," in nums:
                    indices = [int(x) - 1 for x in nums.split(",")]

                elif len(nums) == 1:
                    indices = [int(nums) - 1]

                elif nums == "":
                    indices = list(range(len(item_list) if item_list else length))
            elif len(nums) > 1 or not nums.isnumeric():
                print("Choose 1")
                continue
            elif nums.isnumeric():
                indices = [int(nums) - 1]

            return indices
        except Exception as e:
            print("Error occured: ", e)


# endregion
