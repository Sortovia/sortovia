# Kodi Sorter – version history

Newest first. Each line says what the update changed for you.

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
