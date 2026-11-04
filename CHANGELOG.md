# Kodi Sorter – version history

Newest first. Each line says what the update changed for you.

## 1.34 – A tidier menu
- **1.34.1** Fixes and a new clean-up:
  - **Converting .cbr to .cbz works on the Xbox.** The pages were read fine, but copying the finished .cbz onto the drive failed ("copying the .cbz failed"). It now copies through Kodi's own temp folder path.
  - **Clean TV library** (in *Kodi library*) removes episode entries that aren't TV episodes: files in Movies, Tutorials or a set-aside folder (`_Replaced`, `_Unpacked`, `_No English`), or ones also listed as movies. Then Kodi removes entries whose files are gone. Files are never deleted, and a backup is made first.
  - "Remove wrong movie entries" is now **Clean movie library**, and it also lets Kodi remove entries whose files are gone.
- **1.34.0** **The menu is now a Kodi folder list, sorted into categories**, like other add-ons: *Sort my downloads*, *YouTube*, *Tidy my library folders*, *Kodi library* and *Help & settings*. Each entry has a short description. Opening Kodi Sorter still checks for updates and backs up the library first. A sort that's running, or one to resume, shows at the top.
  - **Pause YouTube downloads:** pause one download or all of them in *Downloads*, and carry on later from where they got to.
  - **Tidy my TV folder / Tidy my Movies folder:** puts what's already there into the folders and names Kodi expects. You see the full list first, and nothing is replaced without asking.

## 1.33 – Comics
- **1.33.1** **Remove wrong movie entries:** under *Kodi library* on the start menu. It finds movies that are really TV episodes, for example "Cesium Hollow" left behind after the whole drive was scanned as Movies. It shows the list and removes them all at once. Only the library entries are removed, never the files, and a library backup is made first. The start menu item is now called "Kodi library: back up, restore, remove wrong movies".
  - The Comics "tidy the folder" line no longer names Ironclad. It only ever moves what's out of place.
- **1.33.0** New start menu item: **Comics: tidy folders, convert .cbr to .cbz, turn pages**.
  - **Tidy the folder:** loose comics go into their series folder, and near-duplicate folders like "Ironclad (2)" are merged into "Ironclad". PDFs that an old version filed in Comics (bills, manuals) can be moved to a Documents folder. You see the list first.
  - **Convert .cbr to .cbz:** Kodi opens a .cbz by itself, page by page. A .cbr needs the Archive support add-on to unpack it first, which is slow and sometimes fails. The .cbr is deleted only after the new .cbz checks out. New .cbr comics are converted while sorting (you can turn this off).
  - **Turn pages for a monitor on its side:** each JPEG page gets an orientation tag, so Kodi shows it turned. Nothing is re-encoded, and "Upright" undoes it. Try one comic first.

## 1.32 – Library backup
- **1.32.0** **Back up / restore my Kodi library** on the start menu.
  - A backup holds Kodi's own library export (shows, episodes, movies, watched marks and resume points) plus a copy of Kodi's database file.
  - It's saved on the Xbox (Home folder → Kodi library backups), on your library drive (`_Kodi library backups`) and on the phone (`Download/KodiSorterBackups`). The newest 5 are kept on the Xbox and the drive.
  - It **backs up by itself once a day** when Kodi Sorter opens, in the background. An empty library is never backed up, so a good backup is never pushed out.
  - If the library **suddenly loses half its episodes or movies**, for example after changing a source's content type, it warns you and shows how to put the backup back (Kodi: Settings → Media → Library → Import library).
  - **YouTube search** shows when each video came out and how many views it has. A new menu item, **Search results order**, sorts by best match, newest, most viewed, longest or shortest. Search is also quicker, because it asks YouTube directly.

## 1.31 – YouTube download quality
- **1.31.4** **Downloads and search results fit on screen.** Each entry has two short lines: the title, then its progress or its length and channel. Nothing scrolls, so pressing down moves to the next entry straight away. A failed download has **Show the whole error**.
  - Search asks YouTube for 20 results instead of 25, which saves one slow request. If the phone's internet is very slow, it says so plainly instead of showing a long command.
- **1.31.3** **Opens faster, with a start-up screen.** It shows "Starting... Checking for updates" straight away instead of nothing. The logs go to the phone in the background while it checks for updates, so it's ready a few seconds sooner. **Cancel** skips the update check, and a second click while it's opening is ignored.
- **1.31.2**
  - **Sorting YouTube downloads goes straight to your default folder.** You choose it once, and change it under "Where sorted videos go" in the YouTube menu. Before, it asked every time, because it ignored Xbox drive paths.
  - **No library rescan** when a run only moved tutorials or comics. They aren't in Kodi's library.
  - Titles in the Downloads list no longer show boxes, and "｜｜" becomes " - " instead of "--".
- **1.31.1** Better at YouTube titles:
  - "walkthrough", "webinar", "quick start" and "getting started" count as tutorials.
  - Producer Pal goes to Ableton Live, Claude Desktop to Claude, and "20⧸20" or "2020 software" to 2020 Design.
  - Emoji and the downloader's look-alike characters (⧸ ｜ ：), which show as boxes on the Xbox, are removed from file names.
  - The preview shows names without %20 codes, and a skipped YouTube video gives the real reason instead of "too small".
- **1.31.0** **Download quality** in the YouTube menu: best up to 4K, 1080p (the default), 720p, 480p, or sound only (.m4a). Lower quality makes smaller files and uses less mobile data. The setting is kept on the phone, and each queued video remembers the quality it was queued with.

## 1.30 – Your language
- **1.30.1** Fixes:
  - **Scans crashed** in 1.30.0 (a mistake in the movie-title lookup). Fixed, and a new test now loads every add-on file.
  - **Import cookies now** in the YouTube menu, with a plain message: imported, already have them, or no file found. A note also pops up whenever new cookies are picked up.
  - Downloads YouTube sends in pieces show progress (pieces done, MB) instead of 0%.
  - Hidden folders (like `.adblocker_1dm`) are skipped when scanning.
- **1.30.0** Choose **your language** on the welcome screen or under Help → Your language. You can pick one or use **Kodi's language**.
  - Kodi Sorter keeps videos with audio in that language. Ones without go to `_No Spanish` and so on, or are skipped or deleted as you choose.
  - It keeps subtitles in that language, and names movies by their title in that language (TMDb).
  - Untagged audio tracks only count as English when English is your language.
  - The YouTube cookie guide now explains how to add an extension from its file when **Add to Firefox** is greyed out.

## 1.29 – Companion app ready
- **1.29.1** Fixes from the first run on the Xbox:
  - **Library folders** show where the standard folders are (for example `E:\Movies`).
  - **The guide** no longer breaks sentences across lines.
  - A folder whose videos are already in Kodi's library is no longer reported as "not a Kodi video source".
- **1.29.0** Kodi Sorter also finds the phone when it runs the new **Kodi Sorter companion** Android app instead of xbox-share in Termux.

## Phone setup
- **YouTube helper (Nov 3):** dropped connections ("Did not get any data blocks") retry by themselves, up to 3 times per video, keeping what was already downloaded. Pieces are retried 30 times before that.

- **One-step install for the phone (Nov 2026):** paste one line into Termux. Ubuntu isn't needed any more. It installs the Wi-Fi share, the YouTube downloader and the `xbox-share` command, and keeps the password from an older setup. See the README, section 3.

## 1.28 – Can Kodi read your folder?
- **1.28.1** **Search & download from YouTube** and **Help** are on the start menu from the very first run, so you don't need to sort something first.
- **1.28.0** When you pick an existing TV or Movies folder, Kodi Sorter checks it against Kodi's library:
  - how many videos Kodi already has,
  - whether the folder is a video source with the right content type,
  - which files have names Kodi can't read.

  If anything's wrong, it explains how to fix it and offers to **reorganize the folder into Kodi-style folders**, in place. It shows how many files would move and roughly how long that takes, and the usual preview comes first. Safe choices are used: it asks before replacing anything, skips the audio check, leaves NFOs and subtitles alone, and doesn't change "Same as last time".

## 1.27 – Use your existing library folders
- **1.27.0** Each kind (TV, Movies, Comics, Tutorials) can go into **a folder you already have**, with any name on any drive. You choose them on the welcome screen or under Help → My library folders. Nothing already in them is moved.
  - New files reuse your **existing show, season and movie folders**: *Sams Sandwiches* → your *Sam's Sandwiches*, *Season 01* → your *Season 1*, *Matrix 1999* → your *The Matrix (1999)*.
  - Years must agree, so *Doctor Who (2005)* never lands in *Doctor Who (1963)*.

## 1.26 – Welcome screen and Help
- **1.26.0** First run shows a **welcome screen**:
  - Choose **what to sort** (TV, Movies, Comics, Tutorials). Kinds you leave unticked are skipped and listed in the preview.
  - It offers to show **the guide** (this README) on the TV.
  - New **Help** menu item: the guide, the version history and "what to sort".
  - After each update, a short **what's new** note.

## 1.25 – Download from YouTube
- **1.25.0** New menu item, **Download from YouTube**:
  - Search YouTube or type a link (a video or a playlist) on the Xbox. The phone downloads it into `Download/YouTube` (up to 1080p, in a format the Xbox plays).
  - Uses a `cookies.txt` exported from your signed-in browser.
  - The queue shows live progress. You can stop or retry a download, then sort the finished videos straight into your library.

## 1.23 – 1.24 – Tutorials
- **1.24.0** You can sort straight from a YouTube download folder (NewPipe, Seal and others). A video there that names a known program is filed as a tutorial even without the word "tutorial". Anything else in that folder is left alone instead of being guessed as a movie.
- **1.23.1** Tutorial folders for Ableton Live, Claude Code, OpenClaw and 20/20 Design.
- **1.23.0** Tutorials go to `Tutorials\<program>\` (AutoCAD, Revit, SketchUp, Blender …) with their original names. Short tutorial videos are no longer skipped as samples.

## 1.22 – Quality tags, credits clips, separate audio
- **1.22.4** A separate audio track is only brought along when the video has no English audio of its own.
- **1.22.3** Separate audio tracks (`.mka/.ac3/.eac3/.dts`) go next to their video, so Kodi offers them as an extra track.
- **1.22.2** Opening/ending credits clips with a show name go to Season 00 instead of being skipped.
- **1.22.1** Checks that `.nomedia` files were really written.
- **1.22.0** New NFO choice: movie `.nfo` files with **quality tags** (codec, 10-bit, source, bit rate).

## 1.21 – Cleaner leftovers, English titles
- **1.21.3** `.nomedia` in `_Unpacked`, `_Replaced` and `_No English`, so Kodi's library scan skips them.
- **1.21.2** Exact duplicates of library files and junk files are cleared. URL-style names (`%5b…`) are decoded. Every action is counted in the report.
- **1.21.1** English titles for Russian movie names written in Latin letters (e.g. *Bolshoi Gorod 3* → *Road Deputies 3*).
- **1.21.0** Option to remove empty folders from the source. It now says when movie titles weren't checked, and offers to set up the TMDb key.

## 1.20 – Subtitle languages
- **1.20.1** Shows progress for the steps after the scan (matching subtitles, checking the library).
- **1.20.0** Keep only the subtitle languages you choose. The others are deleted or parked.

## 1.19 – Destination folders
- **1.19.1** Much faster when moving many small files (subtitles).
- **1.19.0** The destination can be the Movies or TV folder itself. The other kinds go to the folders next to it.

## 1.18 – Comics and movie titles
- **1.18.0** Comics go into series folders. Movies named in another language get their English title (TMDb).

## 1.17 – Subtitles
- **1.17.0** Subtitles go to `Subs\` next to their video. Subtitles named only by language are matched to the right video. Release folders that were sorted earlier get tidied up.

## 1.15 – 1.16 – NFO files
- **1.16.1** Clearer warning when the destination is the Movies or TV folder.
- **1.16.0** Release `.nfo` files are used to tell a video's audio language when the file itself doesn't say.
- **1.15.0** Release NFOs become Kodi `.nfo` files (IMDb links). Leftovers are tidied and empty folders removed.

## 1.13 – 1.14 – Library tools
- **1.14.1** View any text or NFO file (old DOS art shows correctly).
- **1.14.0** **Where to watch**: per season, whether a show is on your services, free, or available to buy or rent (TMDb, free key).
- **1.13.0** **Find missing episodes** in your Kodi TV library (TVmaze). The report is saved to the phone.

## 1.12 – Phone and Xbox fixes
- **1.12.10** PDFs and EPUBs only count as comics inside a Comics or Manga folder (no more bills filed as comics).
- **1.12.9** Updates download as soon as they're released.
- **1.12.8** Sends the log when opened during a background move.
- **1.12.7** Guards against picking the TV folder as the destination. Files already in place are left alone.
- **1.12.6** Resume never deletes a finished copy.
- **1.12.5** Sort a drive in place (source = destination).
- **1.12.4** Finds the phone on the hotspot by itself.
- **1.12.3** Asks for the xbox-share password at start-up.
- **1.12.2** Choose **Stop now** or **Stop after this file**.
- **1.12.1** Works with the Xbox's drives, which can't rename files: copies go straight to the final name.
- **1.12.0** Kodi's logs are sent to the phone automatically.

## 1.9 – 1.11 – Background moves and the phone
- **1.11.1** Shows each step after a copy, so a hang can be traced.
- **1.11.0** Progress bar for each file (GB done, speed, time left). You can stop in the middle of a file.
- **1.10.0** Read downloads from the phone over Wi-Fi (xbox-share), or from a USB drive on the phone (FTP).
- **1.9.0** Moves run in the background while Kodi stays usable.

## 1.4 – 1.8 – Self-update, archives, resume
- **1.8.0** Full run report in Kodi's log.
- **1.7.x** OVAs and specials go to Season 00. Videos inside `.zip/.rar/.7z` are unpacked. An unfinished run can be resumed. The last settings are remembered. More reliable update checks. Clearer scan counts.
- **1.5.x** **Checks for updates** on every start and installs them. Notes are listed once per show. Textless openings are skipped.
- **1.4.0** "Scan finished" menu, scan progress, and scans that can be stopped and carried on.

## 1.0 – 1.3 – First versions
- **1.3.1** Version number shown in the dialog titles.
- **1.3.0** Fansub anime names (*Tinman Meadow*, *Paragon*) sort correctly. The add-on and the command-line tool share the same naming rules.
- **1.2.1** First Kodi add-on for the Xbox: TV, Movies and Comics with a preview, English-audio check and duplicate handling.
- Command-line `kodi_sort.py` with tests.
