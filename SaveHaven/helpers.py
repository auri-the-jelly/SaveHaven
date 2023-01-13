# region Imports
import os
import shutil
import json
import configparser
import sqlite3

from appdirs import user_config_dir
from datetime import datetime

import google.auth
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive']
from configs import creds
config_dir = user_config_dir("SaveHaven", "Aurelia")
if not os.path.exists(config_dir):
    os.mkdir(config_dir)


# endregion
# region Classes

class SaveDir:
    '''
    Object to store name, path and modified time of a folder

    Attributes
    ----------
    name : str
        Name of the folder

    path: str
        Path of the folder

    modified: str
        Last modified time of folder
    '''

    def __init__(self, name, path, modified):
        self.name = name
        self.path = path
        self.modified = modified

    def __str__(self):
        return f"Name: {self.name}\n Path: {self.path}\n Last modified: {self.modified}"

# endregion

# region Drive Functions
def mod_time(file_id: str) -> datetime:
    ''' 
    Returns when a given file was last modified

    Parameters
    ----------

    file_id: str
        ID of the Google Drive file

    Returns
    -------
    date_time_obj: datetime
        Datetime object of last modified time
    '''
    try:
        # create drive api client
        service = build('drive', 'v3', credentials=creds)

        file = service.files().get(fileId=file_id, fields='modifiedTime').execute()
        modified_time = file['modifiedTime']
        date_time_obj = datetime.strptime(modified_time, '%Y-%m-%dT%H:%M:%S.%fZ')
        return date_time_obj

    except:
        print("Failed")

def search_file(mime_type: str, filename: str) -> str:
    '''
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
    '''
    try:
        service = build('drive', 'v3', credentials=creds)
        files = []
        page_token = None
        while True:
            # pylint: disable=maybe-no-member
            response = service.files().list(q=f"mimeType='{mime_type}' and name=\'{filename}\'",
                                            spaces='drive',
                                            fields='nextPageToken, '
                                                    'files(id, name)',
                                            pageToken=page_token).execute()
            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        
    except HttpError as error:
        print(F'An error occurred: {error}')
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
            return folder_id[0]['id']

    except HttpError as error:
        print(F'An error occurred: {error}')
        files = None

    try:
        # create drive api client
        service = build('drive', 'v3', credentials=creds)
        if parent:
            file_metadata = {
                'name': filename,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent]
            }
        else:
            file_metadata = {
                'name': filename,
                'mimeType': 'application/vnd.google-apps.folder',
            }

        # pylint: disable=maybe-no-member
        file = service.files().create(body=file_metadata, fields='id'
                                        ).execute()
        return file.get('id')

    except HttpError as error:
        print(F'An error occurred: {error}')
        return None

def list_folder(folder_id: str) -> list:
    '''
    Lists contents of Google Drive Folder

    Parameters
    ----------
    folder_id: str
        ID of the folder

    Returns
    -------
    files: list
    List of files in the folder
    '''
    try:
        service = build('drive', 'v3', credentials=creds)
        files = []
        page_token = None
        while True:
            # pylint: disable=maybe-no-member
            response = service.files().list(q=f"'{folder_id}' in parents",
                                            spaces='drive',
                                            fields='nextPageToken, '
                                                    'files(id, name, modifiedTime)',
                                            pageToken=page_token).execute()
            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break

        return files

    except HttpError as error:
        print(F'An error occurred: {error}')
        files = None

def upload_file(path: str, name: str, parent: str = None) -> str:
    '''
    Uploads file to Google Drive

    Parameters
    ----------
    path: str
        Path to the file to be uploaded

    name: str
        Name of the file to be uploaded

    parent: str, optional
        ID of the parent Google Drive folder
    '''
    file_id = None
    try:
        service = build('drive', 'v3', credentials=creds)

        # Create the media upload request
        media = MediaFileUpload(path, resumable=True)

        # Perform the upload
        file = service.files().create(body={'name': name, 'parents': [parent]}, media_body=media, fields='id').execute()

        file_id = file.get("id")
    
    except HttpError as error:
        print(F'An error occurred: {error}')
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
        service = build('drive', 'v3', credentials=creds)

        service.files().delete(fileId=file_id).execute()
        return True
    except HttpError as error:
        print(F'An error occurred: {error}')
        return False


# endregion

# region SaveSync functions
def heroic_sync(save_dirs: list, root: str):
    for selected_game in save_dirs:
        heroic_folder = create_folder("Heroic", parent=root)
        files = list_folder(heroic_folder)
        cloud_file = [file for file in files if file['name'] == selected_game.name + '.zip']
        # heroic_db = sqlite3.connect(config_dir + 'heroic.db')
        # db_cur = heroic_db.cursor()
        if len(cloud_file) > 0:
            date_time_obj = datetime.strptime(cloud_file[0]['modifiedTime'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime("%s")
            if float(date_time_obj) < float(selected_game.modified):
                print("Syncing")
                zip_location = selected_game.path + '.zip'
                if os.path.exists(zip_location):
                    os.remove(zip_location)
                print("Zipping")
                shutil.make_archive(selected_game.path, 'zip', selected_game.path)
                print("Uploading")
                delete = delete_file(cloud_file[0]['id'])
                if delete:
                    file_id = upload_file(zip_location, selected_game.name + '.zip', heroic_folder)
                    print(f"Finished {selected_game.name}")
                    os.remove(zip_location)
                    # db_cur.execute("UPDATE games SET uploaded ? WHERE name = ?", [float(datetime.now().strftime("%s")), selected_game.name])
                else:
                    print("Deletion Failed")
            else:
                print(f"Skipping {selected_game.name}, Google Drive up to date")
            print(f"{float(date_time_obj)} {float(selected_game.modified)}")
        else:
            print(f"Working on {selected_game.name}")

            zip_location = selected_game.path + '.zip'
            if not os.path.exists(zip_location):
                print("Zipping")
                shutil.make_archive(selected_game.path, 'zip', selected_game.path)
            print("Uploading")
            file_id = upload_file(zip_location, selected_game.name + '.zip', heroic_folder)
            print(f"Finished {selected_game.name}")
            os.remove(zip_location)
            # db_cur.execute("UPDATE games SET uploaded ? WHERE name = ?", [float(datetime.now().strftime("%s")), selected_game.name])
        # heroic_db.commit()
        # heroic_db.close()

def search_dir(root: str):
    # TODO: Make this shit readable 
    config = configparser.ConfigParser()
    config.read(os.path.join(config_dir, 'config.ini'))
    print(config['Launchers']['selected'])
    launchers = config['Launchers']['selected'].split(',')
    print(launchers)
    home_path = os.path.expanduser("~")
    if 'Games' in os.listdir(home_path) and "Heroic" in launchers:
        games_dir = os.path.join(home_path, "Games")
        heroic_dir = os.path.join(games_dir, "Heroic", "Prefixes")
        heroic_db = sqlite3.connect(config_dir + 'heroic.db')
        db_cur = heroic_db.cursor()
        heroic_saves = []
        for file in os.listdir(heroic_dir):
            if os.path.isdir(os.path.join(heroic_dir,file)):
                save_path = os.path.join(heroic_dir, file)
                heroic_saves.append(SaveDir(file, save_path, os.path.getmtime(save_path)))
        print("Found Heroic game saves:")
        db_saves = db_cur.execute("SELECT * FROM games")
        for i in range(len(heroic_saves)):
            '''
            if heroic_saves[i].name not in [x for x['name'] in db_saves]:
                db_cur.execute("INSERT INTO games VALUES ('?', '?', ?)", (heroic_saves[i].name, heroic_saves[i].path, '0'))
                heroic_db.commit()
                heroic_db.close()'''
            print(f"{i+1}. {heroic_saves[i].name}")

        while True:
            sync_nums = input("Enter range (3-5) or indexes (1,3,5): ")
            valid_chars = "1234567890-,"
            valid = True
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
            if sync_nums.count('-') > 1 or ('-' in sync_nums and ',' in sync_nums):
                print("Specify no more than range, or use list")
                continue
            try:
                if '-' in sync_nums:
                    indices = range(int(sync_nums.split('-')[0]), int(sync_nums.split('-')[1]) + 1)

                elif ',' in sync_nums:
                    indices = sync_nums.split(',')

                elif len(sync_nums) == 1:
                    indices = [int(sync_nums)]

                elif sync_nums == '':
                    indices = range(1, len(heroic_saves) + 1)

                print("Backing up these games: ")
                for i in range(len(indices)):
                    indices[i] = int(indices[i]) - 1
                    print(heroic_saves[indices[i]])
                break
            except Exception as e:
                print("Error occured: ", e)
            

        selected_games = [heroic_saves[index] for index in indices]
        heroic_sync(selected_games, root)
            
def update_launchers(launchers: list):
    config = configparser.ConfigParser()
    config['Launchers'] = {'selected': ','.join(launchers)}
    return config

# endregion