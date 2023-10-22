from helpers import *

for files in os.listdir(heroic_dir):
    if os.path.isdir(os.path.join(heroic_dir, files)):
        save_path = os.path.join(heroic_dir, files)
        game_name = save_path.split("/")[-1]
        print(game_name)
        pcgw = pcgw_search(game_name)
        temp_locations = [
            pcgw_loc[1]
            for pcgw_loc in pcgw.items()
            if pcgw_loc[0]
            in ["Windows", "Epic Games", "Epic Games Store", "Epic Games Launcher"]
        ]
        locations = []
        for loc in temp_locations:
            locations.append(loc)
            if "Documents" in loc:
                short_loc = loc[: loc.find("/", loc.index("Documents") + 10) + 1]
                locations.extend(
                    (
                        short_loc,
                        f"{short_loc[:loc.index('Documents') + 10]}My Games/{short_loc[loc.index('Documents') + 10:]}",
                    )
                )
        for location in locations:
            try_path = os.path.join(save_path, location)
            if os.path.exists(try_path):
                print(try_path)
                break
        # .../Documents/Payday 2/
        #              ^        ^
        # index("Documents" + 10) loc[loc.index("Documents") + 10:]].index("/")
        """
        save_location = os.path.join(save_path, pcgw["Windows"])
        if os.path.exists(save_location):
            print(os.listdir(save_location))
        else:
            doc_loc = save_location.rfind("Documents")
            if doc_loc != -1:
                search_location = save_location.split("/")
                search_location = search_location[
                    search_location.index("Documents") + 1
                ]
                save_location = save_location[: doc_loc + 10] + search_location
                print(save_location)
                if os.path.exists(save_location):
                    print(os.listdir(save_location))
                else:
                    save_location = save_location.replace(
                        "Documents", "Documents/My Games"
                    )
                    if os.path.exists(save_location):
                        print(os.listdir(save_location))"""

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
