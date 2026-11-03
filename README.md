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
- Audio language check: videos with **no English audio** can be skipped, moved to `_No English`, or deleted.
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

**Library extras**
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
- whether you **already have folders** for them (pick each one, any name, any drive),

and offers this guide. You can change all of these later under **Help** in the start menu.

Next time, the start menu offers **Same as last time** and the extra tools.

Optional: when you first use a TMDb feature (English movie titles, Where to watch), it asks for a free TMDb API key, your
country and your streaming services.

### 3. The phone (Android with Termux), optional

This lets the Xbox read the phone's Download folder, send its logs there and download from YouTube.

1. Install **Termux** (from F-Droid), then install Ubuntu inside it with `proot-distro`, and inside Ubuntu run
   `apt install rclone`.
2. Install the `xbox-share` command from this repository:
   - in plain Termux: `cp tools/termux-xbox-share $PREFIX/bin/xbox-share`. It starts the Ubuntu one and keeps
     the phone awake.
3. Turn on the phone's **Mobile hotspot** and connect the Xbox to it.
4. Run **`xbox-share`** in Termux. It shows a password. Kodi Sorter finds the phone by itself and asks for
   that password once.
5. Keep Termux open while files copy.

For a USB drive plugged into the phone, use the *primitive ftpd* app (F-Droid) and choose
"USB drive on the phone" in Kodi Sorter.

### 4. Download from YouTube, optional

1. In plain Termux, run `pkg install yt-dlp ffmpeg nodejs`.
2. **Cookies (once, and again when downloads start failing):** YouTube only allows downloads from a signed-in browser.
   1. In Firefox on the phone, add the **cookies.txt** (or *Get cookies.txt LOCALLY*) extension.
   2. Sign in to youtube.com in a **private tab**.
   3. Export the cookies for that site into **Download**, then close the private tab.

   The phone's helper moves the file out of the shared folder and uses it from there. Treat this file like a
   password: it's your YouTube sign-in.
3. Start `xbox-share`. It also starts the YouTube helper.
4. In Kodi Sorter, choose **Download from YouTube**, then:
   - **Search YouTube** or **Type a link** (a video or a playlist),
   - **Downloads** to watch progress,
   - **Sort the finished downloads** to put them into `Tutorials`.

Only download videos you're allowed to keep: your own, or ones the creator permits.

---

## Other tools in this repository

| Path | What it is |
|---|---|
| `addon/script.kodisorter/` | the Kodi add-on (`default.py`; naming rules in `sortlib.py`) |
| `kodi_sort.py` | command-line version for a PC or phone (`python3 kodi_sort.py --src SRC --dest DEST`; dry run unless `--go`) |
| `tools/xbox_share.sh` | the phone's WebDAV share for the Xbox |
| `tools/yt_helper.py` | the phone's YouTube download helper (started by xbox-share, port 8081) |
| `tools/build_kodi_repo.py` | builds the zips for the Kodi repository site |
| `tests/` | `python3 -m unittest discover -s tests` |

## Version history

See [CHANGELOG.md](CHANGELOG.md) for what each update added. In Kodi: Kodi Sorter → **Help** → Version history.
