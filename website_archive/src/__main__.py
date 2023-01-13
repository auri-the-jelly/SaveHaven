# region Import image utilities
from steamgrid import SteamGridDB
import os
from PIL import Image
import requests
import shutil
# endregion

# region Import the GTK module
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf
# endregion
sgdb = SteamGridDB('c9252f7b1dc042ef1f242443876eabc0')
image_path = {}
login = False
def get_image(game_title):
    grids = sgdb.get_grids_by_gameid([sgdb.search_game(game_title)[0].id])
    for grid in grids:
        if grid.height > grid.width:
            grids = grid
            print(dir(grids))
            break

    res = requests.get(grids, stream = True)
    image_path[game_title] = os.path.join("grid/", str(grids.id) + grids.url[-4:])

    if res.status_code == 200:
        with open(image_path[game_title],'wb') as f:
            shutil.copyfileobj(res.raw, f)
        print('Image sucessfully Downloaded: ')
    else:
        print('Image Couldn\'t be retrieved')

    with Image.open(image_path[game_title]) as im:
        im_resized = im.resize((im.width // 5, im.height // 5))
        im_resized.save(image_path[game_title])

    print(grids)

def create_button(game_title):
            # Create a new Gtk.Image and set the image file
            get_image(game_title)
            image = Gtk.Image()
            image.set_from_file(image_path[game_title])
            imageButton = Gtk.Button(label=game_title)
            imageButton.set_image(image)
            imageButton.set_image_position(Gtk.PositionType.TOP)
            imageButton.set_always_show_image(True)
            return imageButton

# Create a new window
class MainWindow(Gtk.Window):

    def __init__(self):
        super().__init__(title = "Help")
        self.set_border_width(10)

        # window.add(label)
        # Create a new Gtk.Box to hold the image and label
        self.box = Gtk.Box(spacing = 10)
        if login:
            self.imageButtons = []
            self.imageButtons.append(create_button("Batman: Arkham Knight"))
            self.imageButtons.append(create_button("Subnautica"))
            self.imageButtons.append(create_button("Skyrim"))
            for imageButton in self.imageButtons:
                imageButton.connect("clicked", self.on_image_clicked)
                self.box.add(imageButton)
            
        else:
            pass

        # Add the box to the window
        self.add(self.box)

    def on_image_clicked(self, widget):
        print("Hey")

        

window = MainWindow()
# Show the window and start the GTK main loop
window.connect("destroy", Gtk.main_quit)
window.show_all()
Gtk.main()
