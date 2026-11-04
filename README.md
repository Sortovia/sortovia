# Kodi Sorter

Kodi Sorter is a Kodi add-on that tidies a pile of downloads into the folder layout Kodi expects, so the
Kodi library recognises everything. It was built for Kodi on an **Xbox** (Kodi 21, UWP) with an Android phone as
helper, and works with any Kodi that can see your drives.

```
E:\
├── TV\Show Name (Year)\Season 01\Show Name (Year) S01E02.mkv
├── Movies\Movie Name (Year)\Movie Name (Year).mkv
├── Comics\Series\<original file>.cbz
└── Tutorials\AutoCAD\<original file>.mp4
```

**Already have a library?** You can point each kind at your own folders, with any name on any drive
(for example `D:\My Shows`, `F:\Films`). New files are added to them, and nothing already there is moved. Inside
those folders it reuses your existing show, season and movie folders: "Sams Sandwiches S15E01" goes into your
`Sam's Sandwiches\Season 15`, not into a new near-duplicate folder.

When you pick an existing TV or Movies folder, Kodi Sorter **checks whether Kodi's library can read it**:
- how many of its videos are already in the library,
- whether the folder is set up as a Kodi video source at all,
- which files have names Kodi can't read (no episode number, no year, not inside a show folder).

If something's wrong, it tells you how to fix it and offers to **reorganize the folder into Kodi-style folders**, in
place. You see the full list before anything moves.

Before anything moves, it shows you the plan. Nothing is overwritten without your OK. Replaced copies go
to `_Replaced`, and leftovers from releases go to `_Unpacked`, so you can delete them later.

---

## Features

**Sorting and naming**
- TV episodes (`S01E02`, `1x02`, fansub `Show - 07`, double episodes) go to `TV\Show\Season NN\`.
- Movies (a title plus a year) go to `Movies\Title (Year)\`. With a TMDb key, a movie named in another
  language gets its English title, including Russian titles written in Latin letters.
- OVAs, specials, and opening/ending credits clips go to Season 00, which is Kodi's Specials.
- Comics (`.cbz/.cbr/.cb7/.cbt`, plus PDFs/EPUBs inside a "Comics" or "Manga" folder) go to `Comics\Series\`.
  `.cbr` comics become `.cbz`, which Kodi opens much faster. The Comics menu also tidies an existing Comics folder and
  can turn pages for a monitor stood on its side (portrait).
- **Tutorials** go to `Tutorials\<program>\` and keep their original names. A video counts as a tutorial when:
  - its name says so ("tutorial", "full course", "for beginners" and similar), or
  - it sits in a `Tutorials\<program>` folder, or
  - it comes from a YouTube download folder (NewPipe, Seal and others) and names a known program.

  Known programs include AutoCAD, Revit, Civil 3D, SketchUp, Blender, Fusion 360, SolidWorks, 3ds Max, Rhino,
  Photoshop, Excel, Ableton Live, Claude Code, OpenClaw, 20/20 Design and more. Anything else goes to `Other`.
- Subtitles go to `Subs\` next to their video, with a language tag. Subtitles named only by language
  (`2_English.srt`) are matched to the right video. You can keep only the languages you choose.
- Separate audio tracks (`.mka/.ac3/.eac3/.dts`) are placed next to their video, but only when the video
  has no English audio of its own.
- Download-site prefixes, release tags and junk words are stripped from names. Names are made safe for NTFS and exFAT.

**Choosing between copies**
- Duplicates: keeps the better copy. English audio wins first, then the higher resolution, then the bigger file.
  You choose whether it asks you, always replaces, or never replaces.
- Audio language check: videos with **no audio in your language** (English unless you choose another) can be
  skipped, moved to `_No English` (or `_No Spanish` ...), or deleted.
  It reads the file's own audio tracks. When the tracks don't say, it reads the release's `.nfo`.
- Samples (videos under 50 MB, or named "sample") are left alone. Tutorials are exempt from the size limit.

**Archives and leftovers**
- Videos inside `.zip`, `.rar` and `.7z` archives are unpacked. `.rar` and `.7z` need Kodi's *Archive support* add-on.
- Release `.nfo` files become Kodi `.nfo` files using their IMDb links. You can also add quality tags (codec,
  10-bit, source, bit rate) to movie `.nfo` files.
- Tidy-up afterwards: leftovers go to `_Unpacked`, exact duplicates and empty folders are removed, and `.nomedia`
  files are added so Kodi's library scan skips the park folders.

**Running it on the Xbox**
- Moves run in the background with a progress bar for each file (GB done, speed, time left). Kodi stays usable while it works.
- You can stop now or after the current file. If Kodi quits mid-run, it offers to **Resume** next time, and half copies are cleaned up.
- It can sort a drive in place (source and destination the same), leaving files already in their place untouched.
- It updates itself: every start it checks for a newer version and offers to install it.

**The phone as a helper** (over the phone's hotspot, without using mobile data for transfers)
- It can read downloads straight from the phone's storage (`xbox-share`) or from a USB drive plugged into the phone (FTP app).
- It sends Kodi's logs to the phone automatically (`Download/KodiSorterLogs`).
- **Download from YouTube**: search or type a link on the Xbox. The phone downloads the video with your browser's
  sign-in cookies and saves it to `Download/YouTube`. Kodi Sorter then sorts it into `Tutorials`.

**Real-Debrid** (optional, needs a premium account)
- Sign in with a code on your phone. Pick from your Real-Debrid torrents, add a magnet link, or unlock a
  file-host link. Files download to `Downloads\Real-Debrid` on the library drive in the background, then
  *Sort the Real-Debrid downloads* files them.

**Library extras**
- *Kodi library → Back up*: Kodi's own library export (with watched marks) plus its database file, saved on the
  library drive (`_Kodi library backups`) and the phone, never on the Xbox's small storage. It runs by itself once a
  day, and warns you if the library suddenly shrinks. *Restore a backup* gets one ready for Kodi's Import library.
  *Remove old library backups* frees space.
- *Clean TV library / Clean movie library*: removes entries that are in the wrong library (never files).
- *Find missing episodes*: compares your Kodi TV library with TVmaze and lists aired episodes you don't have.
- *Where to watch*: says per season whether a show is on your streaming services, free with ads,
  on another subscription, or available to buy or rent. This uses TMDb's watch data and needs a free TMDb key.
- *View a text / NFO file*: reads old DOS-style NFO art correctly.

---

## First-time setup

### 1. Install the add-on in Kodi

1. In Kodi, go to **Settings → System → Add-ons** and turn on **Unknown sources**.
2. Go to **Settings → File manager → Add source**. Type `https://akaguyver.github.io/kodi-repo/`
   and name it `kodirepo`.
3. Go to **Settings → Add-ons → Install from zip file → kodirepo** and pick the newest **`script.kodisorter-x.y.z.zip`**.
4. (Recommended) Go to **Add-ons → Install from repository → Kodi Add-on repository → VFS add-ons → Archive support**.
   Without it, `.rar` and `.7z` files can't be unpacked.
5. Open Kodi Sorter from **Add-ons → Program add-ons**. From then on it updates itself.

### 2. First run

1. **Where are the downloads?** Choose a folder or drive on the Xbox, or your phone (see section 3).
2. **Destination:** the drive that holds your library (for example `E:\`), or the Movies/TV folder itself.
3. Answer the questions about better copies, audio language, NFOs, subtitles and leftovers. If you're
   unsure, the first option is the safe one.
4. Read the preview. It lists every move, everything it will skip and why, and notes such as "check the season".
5. Choose **Move now**, in the background if you like. A report is saved, and you can reopen it from the start menu.

The very first time, a welcome screen asks:
- **what you want to sort** (TV, Movies, Comics, Tutorials),
- **your language**: the audio it looks for, the subtitles it keeps and the language of movie titles (English
  unless you choose another, or "Kodi's language"),
- whether you **already have folders** for them (pick each one, any name, any drive),

and offers this guide. You can change all of these later under **Help & settings**.

After that, Kodi Sorter opens a folder list sorted into categories:
- **Sort my downloads**: same as last time, choose folders and choices, the last report,
- **YouTube**: search, links, downloads (pause, carry on, retry), quality, order, cookies,
- **Tidy my library folders**: TV, Movies and Comics folders; .cbr to .cbz; turning comic pages,
- **Kodi library**: backup and restore, removing wrong movie entries, missing episodes, where to watch,
- **Help & settings**: the guide, version history, what to sort, your folders and language, updates, logs.

Optional: when you first use a TMDb feature (English movie titles, Where to watch), it asks for a free TMDb API key, your
country and your streaming services.

### 3. The phone (Android), optional

This lets the Xbox read the phone's Download folder, send its logs there and download from YouTube.

1. Install **Termux** from **F-Droid** (https://f-droid.org/packages/com.termux/) or from Termux's GitHub page.
   The Play Store version is outdated and doesn't work.
2. Open Termux and paste this one line:

   ```
   pkg install -y curl && curl -fsSL https://akaguyver.github.io/kodi-repo/phone/install.sh | bash
   ```

   It installs everything (a few minutes the first time). Tap **Allow** when Android asks about storage. It ends by
   showing your password. Run the same line again any time to update.
3. Turn on the phone's **Mobile hotspot** and connect the Xbox to it.
4. In Termux type **`xbox-share`**. Kodi Sorter on the Xbox finds the phone by itself and asks for the password once.
5. Keep Termux open (in the background is fine) while you use it.

For a USB drive plugged into the phone, use the *primitive ftpd* app (F-Droid) and choose
"USB drive on the phone" in Kodi Sorter.

### 4. Download from YouTube, optional

1. The installer above already set up everything YouTube needs.
2. **Cookies (once, and again when downloads start failing):** YouTube only allows downloads from a signed-in browser.
   1. In Firefox on the phone, open addons.mozilla.org, search for **cookies.txt** (the one called just that; it works on Android) and tap **Add to Firefox**.
   2. **If Add to Firefox is greyed out** (for example *Get cookies.txt LOCALLY*, which isn't marked for Android), install it from its file:
      - Firefox → Settings → About Firefox, and tap the Firefox logo **5 times** to turn on the debug menu.
      - Back in Settings, choose **Install extension from file** and pick the `.xpi` file from Download. Only signed files from addons.mozilla.org install.
   3. Allow the extension in private tabs: Extensions → the extension → Settings → *Run in private browsing*.
   4. Open a **private tab**, sign in to youtube.com, and export the cookies for that site (Netscape format) into **Download**. Then close the tab without signing out.

   The phone's helper moves the file out of the shared folder and uses it from there. Treat this file like a
   password: it's your YouTube sign-in. The same steps are in Kodi Sorter → Search & download from YouTube →
   How to set up cookies.
3. Start `xbox-share`. It also starts the YouTube helper.
4. In Kodi Sorter, choose **Download from YouTube**, then:
   - **Search YouTube** or **Type a link** (a video or a playlist),
   - **Downloads** to watch progress,
   - **Download quality**: up to 4K, 1080p (default), 720p, 480p or sound only,
   - **Search results order**: best match, newest, most viewed, longest or shortest. Each result shows its length, when it came out, its views and its channel,
   - **Where sorted videos go**: chosen once (for example `E:\Tutorials`); sorting then goes straight there,
   - **Sort the finished downloads** to put them into `Tutorials`.

Only download videos you're allowed to keep: your own, or ones the creator permits.

---

## Other tools in this repository

| Path | What it is |
|---|---|
| `addon/script.kodisorter/` | the Kodi add-on (`default.py`; naming rules in `sortlib.py`) |
| `kodi_sort.py` | command-line version for a PC or phone (`python3 kodi_sort.py --src SRC --dest DEST`; dry run unless `--go`) |
| `tools/phone/install.sh` | one-step phone setup for Termux (published at akaguyver.github.io/kodi-repo/phone/) |
| `tools/xbox_share.sh` | the phone's WebDAV share for the Xbox |
| `tools/yt_helper.py` | the phone's YouTube download helper (started by xbox-share, port 8081) |
| `tools/build_kodi_repo.py` | builds the zips for the Kodi repository site |
| `tests/` | `python3 -m unittest discover -s tests` |

## Version history

See [CHANGELOG.md](CHANGELOG.md) for what each update added. In Kodi: Kodi Sorter → **Help** → Version history.

## Credits

QR codes are drawn with [QR Code generator library](https://www.nayuki.io/page/qr-code-generator-library) by
Project Nayuki (MIT licence), included as `qrcodegen.py`.
