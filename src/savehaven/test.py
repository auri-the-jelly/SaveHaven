from helpers import *

Control = pcgw_search("Control")
Arkham = pcgw_search("Batman Arkham City")
IDArkham = pcgw_search("200260", True)


steam_dir = os.path.join(os.path.expanduser("~"), ".steam")

pcgw_api_url = "https://pcgamingwiki.com/api/appid.php?appid="
steam_games = []
for game_title in os.listdir(os.path.join(steam_dir, "steam", "steamapps", "common")):
    if "demo" in game_title:
        game_title = game_title.replace("demo", "")
    if "Proton" not in game_title and "Steam" not in game_title:
        save_loc = pcgw_search(game_title)
