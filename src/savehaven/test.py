from helpers import *

for files in os.listdir(heroic_dir):
    if os.path.isdir(os.path.join(heroic_dir, files)):
        save_path = os.path.join(heroic_dir, files)
        game_name = save_path.split("/")[-1]
        print(game_name)
        pcgw = pcgw_search(game_name)
        save_location = os.path.join(save_path, pcgw["Windows"])
        if os.path.exists(save_location):
            print(os.listdir(save_location))
"""
Control = pcgw_search("Control")
Arkham = pcgw_search("Batman Arkham City")
IDArkham = pcgw_search("200260", True)

print(Control)
steam_dir = os.path.join(os.path.expanduser("~"), ".steam")

pcgw_api_url = "https://pcgamingwiki.com/api/appid.php?appid="
steam_games = []
for game_title in os.listdir(os.path.join(steam_dir, "steam", "steamapps", "common")):
    if "demo" in game_title:
        game_title = game_title.replace("demo", "")
    if "Proton" not in game_title and "Steam" not in game_title:
        save_loc = pcgw_search(game_title)"""
