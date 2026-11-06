"""Hold down an artist in Kodi's music library: fix that artist's music tags."""
import sys

import xbmc

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

if __name__ == "__main__":
    name = sys.listitem.getLabel() or xbmc.getInfoLabel("ListItem.Artist")
    xbmc.executebuiltin("RunPlugin(plugin://script.kodisorter/?action=music_tags_artist&artist=%s)" % quote(name.encode("utf-8")))
