# Sortovia

Sortovia (formerly Kodi Sorter) is a free add-on for Kodi that turns a pile of downloads into the folders Kodi understands, so its
library recognises everything:

```
E:\
├── TV\Show Name (Year)\Season 01\Show Name (Year) S01E02.mkv
├── Movies\Movie Name (Year)\Movie Name (Year).mkv
├── Comics\Series\<original file>.cbz
└── Tutorials\AutoCAD\<original file>.mp4
```

**You always see the plan first.** Nothing moves until you say so, and nothing is overwritten without your OK.

---

## Before you start

You need:
- **Kodi 19 or newer**, with an internet connection for the install.
- **Your files on a drive Kodi can see**, and enough free space on the drive they're going to.

That's all. An Android phone, a TMDb key and Real-Debrid are optional extras, and you can ignore them to begin with.

Sortovia is built and tested on **Kodi 21 on an Xbox One S**. It uses Kodi's own file functions, so it should work on
other devices, but they haven't been tested yet. Try it on a few files first.

---

## Install it (about 5 minutes)

1. In Kodi, go to **Settings → System → Add-ons** and turn on **Unknown sources**. Choose **Yes** at the warning.
2. Go to **Settings → File manager → Add source**. Select the box that says `<None>`, type this address, and name it `kodirepo`:

   ```
   https://akaguyver.github.io/kodi-repo/
   ```

3. Go to **Settings → Add-ons → Install from zip file → kodirepo** and pick **`script.kodisorter-x.y.z.zip`**.
4. Recommended: go to **Add-ons → Install from repository → Kodi Add-on repository → VFS add-ons → Archive support**.
   Without it, `.rar` and `.7z` files can't be unpacked.
5. Open **Sortovia** from **Add-ons → Program add-ons**.

From then on, Sortovia offers its own updates when it opens. You can turn that off in its settings.

---

## Your first sort

The first time it opens, a welcome screen asks a few short questions: what device this is, what you want to sort, your
language, whether you already have library folders, and whether you want to use a phone. You can change every answer later
in **Help & settings**.

Then:

1. Open **Sort my downloads → Choose folders and choices**.
2. **Where are the downloads?** Pick a folder or drive.
3. **Where do they go?** Pick the drive that holds your library (for example `E:\`), or your Movies or TV folder.
4. Answer the questions about better copies, audio language, NFOs, subtitles and leftovers. If you're unsure, the first
   option is the safe one.
5. Read the preview. It lists every move, everything it will skip and why, and anything worth checking.
6. Choose **Move now**. You can run it in the background and keep using Kodi.

### Then show Kodi the new folders

Kodi only lists folders you've added as sources. Add **each folder on its own**. In Sortovia,
**Help & settings → How to add your folders to Kodi** has the steps for your device.

| Folder | Where to add it | "This directory contains" |
|---|---|---|
| `TV` | Videos → Files → Add videos | TV shows |
| `Movies` | Videos → Files → Add videos | Movies |
| `Tutorials` | Videos → Files → Add videos | None |
| `Comics` | Pictures | (not asked) |

> **Don't add a whole drive (such as `E:\`) as one source with a content type.** It overrides the folders inside it, and
> Kodi can remove your shows from the library and scan them as movies.

**On an Xbox**, Kodi's Add source browser doesn't list external drives, so type the path into the `<None>` box instead, for example:

```
win-lib://removable/E:\TV\
```

---

## Settings

Open **Help & settings → Settings**.

| Setting | What it does | Starts as |
|---|---|---|
| Check for updates | Looks for a new version each time Sortovia opens | On |
| Daily library backup | Saves Kodi's library to your library drive once a day, if it has changed | On |
| Use an Android phone | Shows the phone and YouTube options, and lets it look for your phone | Your welcome-screen answer |
| Copy logs to the phone | Saves Kodi's logs to the phone's `Download/KodiSorterLogs` folder | On, once a phone is set up |
| TMDb | Your free key, country and streaming services | Not set |

---

## Already have a library?

You can point each kind of file at your own folders, with any name on any drive (for example `D:\My Shows`, `F:\Films`).
New files are added there, and nothing already there is moved. Sortovia reuses your existing show, season and movie
folders: "Sams Sandwiches S15E01" goes into your `Sam's Sandwiches\Season 15`, not a new near-duplicate folder.

When you pick an existing TV or Movies folder, Sortovia checks whether Kodi's library can read it:
- how many of its videos are already in the library,
- whether the folder is set up as a Kodi video source,
- which files have names Kodi can't read.

If something's wrong, it tells you how to fix it and offers to reorganize the folder in place. You see the full list before
anything moves.

---

## Optional: use an Android phone

A phone lets Sortovia read downloads from the phone over Wi-Fi and save Kodi's logs there. It can also download from
YouTube. Kodi's device and the phone must be on the same Wi-Fi, or Kodi's device must be on the phone's hotspot.

| | Companion app | Termux |
|---|---|---|
| Read the phone's Download folder | Yes | Yes |
| Copy logs to the phone | Yes | Yes |
| Download from YouTube | No | Yes |
| Setup | Install one app | Paste one command |

### Easiest: the companion app

1. On the phone, open https://akaguyver.github.io/kodi-repo/app/ and follow the steps to install it.
2. Allow the **Phone settings** it asks for, then tap **Start sharing**.
3. In Sortovia, choose **My phone over Wi-Fi** and type the password the app shows.

### For YouTube too: Termux

1. Install **Termux** from **F-Droid** (https://f-droid.org/packages/com.termux/) or from Termux's GitHub page.
   The Play Store version is outdated and doesn't work.
2. Open Termux and paste this line. Tap **Allow** when Android asks about storage.

   ```
   pkg install -y curl && curl -fsSL https://akaguyver.github.io/kodi-repo/phone/install.sh | bash
   ```

   It takes a few minutes the first time and ends by showing your password. Run the same line again any time to update.
3. Type **`xbox-share`** in Termux. Despite the name, it works with Kodi on any device. Sortovia finds the phone by itself and asks for the
   password once. Keep Termux open in the background while you use it.

Handy commands: `xbox-share password` shows the password, and `xbox-share stop` stops the share. Use only one share at a
time: stop `xbox-share` before using the companion app.

For a USB drive plugged into the phone, use the *primitive ftpd* app (F-Droid) and choose "USB drive on the phone" in Kodi
Sorter.

### Download from YouTube

Only download videos you're allowed to keep: your own, or ones the creator permits. YouTube only allows downloads from a
signed-in browser, so this needs your browser's cookies.

> **Your cookies file works like a password for your Google account.** Consider using a spare account. Automated downloading
> may be against YouTube's terms, and using it is at your own risk.

1. Complete the Termux setup above.
2. In Firefox on the phone, open addons.mozilla.org, search for **cookies.txt** (the one called just that; it works on Android) and tap **Add to Firefox**.
3. **If Add to Firefox is greyed out** (for example *Get cookies.txt LOCALLY*, which isn't marked for Android), install it from its file:
   - Firefox → Settings → About Firefox, and tap the Firefox logo **5 times** to turn on the debug menu.
   - Back in Settings, choose **Install extension from file** and pick the `.xpi` file from Download. Only signed files from addons.mozilla.org install.
4. Allow the extension in private tabs: Extensions → the extension → Settings → *Run in private browsing*.
5. Open a **private tab**, sign in to youtube.com, and export the cookies for that site (Netscape format) into **Download**. Then close the tab without signing out.
6. Start `xbox-share`. The helper moves the file out of the shared folder and uses it from there. Repeat these steps if downloads start failing.
7. In Sortovia, open **YouTube**. You can search or type a link, follow **Downloads**, choose the quality and result order, then **Sort the finished downloads**.

---

## If something goes wrong

**"Couldn't connect" when adding the address, or the zip isn't listed.** Check the address is typed exactly, including the
`https://` and the last `/`, and that Kodi's device is online.

**The drive doesn't appear in the Add source browser (Xbox).** Type the `win-lib://removable/...` path shown above instead
of browsing.

**My shows disappeared from the library or appeared as movies.** A source probably covers the whole drive. Remove that source,
add `TV` and `Movies` separately with the right content types, and scan again. **Kodi library → Clean movie library** removes
TV episodes wrongly listed as movies. Sortovia never deletes your video files for this.

**Kodi closed in the middle of a sort.** Open Sortovia and choose **Resume**.

**Sortovia can't find the phone.** Check the share is running on the phone and that both devices are on the same Wi-Fi or
hotspot. A VPN on the phone can get in the way. If it still can't find it, type the phone's address when asked.

**A file was skipped.** The preview says why. Common reasons: it's under 50 MB (treated as a sample), it has no audio in your
language, or a better copy already exists.

**Something else.** The last sort's report is under **Sort my downloads**, and Kodi's log has more detail in lines containing
`Sortovia`.

---

## What it connects to

Sortovia has no accounts of its own, no ads and no analytics. It connects only to:

| Service | When | What it sends |
|---|---|---|
| GitHub | Update checks and updates | A normal web request |
| TVmaze | *Find missing episodes* | Show names |
| TMDb | English titles, *Where to watch*, if you add a key | Titles and your key |
| Real-Debrid | Only if you sign in | Your links and sign-in token |
| Sites whose feeds you add | When you open *My releases* | A normal web request to the address you added |
| Your phone | Only if you set one up | Files and logs, on your own network |
| YouTube | Only from the phone, if you use YouTube downloads | Your searches, links and cookies |

When the phone is set up, Sortovia looks for it by briefly checking the addresses on your local network. Passwords and keys
are stored unencrypted in Kodi's add-on data on your device.

---

## All the features

**Sorting and naming**
- TV episodes (`S01E02`, `1x02`, fansub `Show - 07`, double episodes) go to `TV\Show\Season NN\`.
- Movies (a title plus a year) go to `Movies\Title (Year)\`. With a TMDb key, a movie named in another
  language gets a title in your language, including Russian titles written in Latin letters.
- OVAs, specials, and opening/ending credits clips go to Season 00, which is Kodi's Specials.
- Comics (`.cbz/.cbr/.cb7/.cbt`, plus PDFs/EPUBs inside a "Comics" or "Manga" folder) go to `Comics\Series\`.
  `.cbr` comics become `.cbz`, which Kodi opens much faster. The Comics menu also tidies an existing Comics folder and
  can turn pages for a monitor stood on its side.
- **Tutorials** go to `Tutorials\<program>\` and keep their original names. A video counts as a tutorial when its name says so
  ("tutorial", "full course", "for beginners" and similar), when it sits in a `Tutorials\<program>` folder, or when it comes
  from a YouTube download folder and names a known program. Anything else goes to `Other`.
- Subtitles go to `Subs\` next to their video, with a language tag. You can keep only the languages you choose.
- Separate audio tracks (`.mka/.ac3/.eac3/.dts`) are placed next to their video when the video has no English audio of its own.
- Download-site prefixes, release tags and junk words are stripped. Names are made safe for NTFS and exFAT.

**Choosing between copies**
- Duplicates: keeps the better copy. English audio wins first, then the higher resolution, then the bigger file.
  You choose whether it asks you, always replaces, or never replaces.
- Audio language check: videos with no audio in your language can be skipped, moved to a `_No English` style folder, or deleted.
- Samples (videos under 50 MB, or named "sample") are left alone. Tutorials are exempt from the size limit.

**Archives and leftovers**
- Videos inside `.zip`, `.rar` and `.7z` archives are unpacked.
- Release `.nfo` files become Kodi `.nfo` files using their IMDb links, and you can add quality tags to movie `.nfo` files.
- Replaced copies go to `_Replaced` and release leftovers go to `_Unpacked`, so you can delete them later. Exact duplicates and
  empty folders are removed, and `.nomedia` files keep Kodi's scan out of those folders.

**While it runs**
- Moves run in the background with progress for each file. Kodi stays usable.
- You can stop now or after the current file. If Kodi quits, it offers to **Resume**, and half copies are cleaned up.
- It can sort a drive in place, leaving files already in their place untouched.

**Real-Debrid** (optional, needs a premium account)
- Sign in with a QR code or a code on your phone. Pick from your Real-Debrid torrents, add a magnet link, or unlock a file-host
  link. Files download to `Downloads\Real-Debrid` on the library drive, then *Sort the Real-Debrid downloads* files them.
- **Automatic downloads:** anything you send to Real-Debrid downloads by itself as soon as it's ready. It works in the
  background, and carries on the next time you open Sortovia if Kodi was closed. The top of the menu shows progress and Stop.
- **My releases:** add the RSS, Atom or JSON feed of your own uploads from any site you use, then tick releases to get them.
  Sortovia includes no sites and sends no searches: it reads only the feeds you add and filters them on your device. Feed
  addresses often contain a private key, so treat them like passwords. Only fetch what you have the right to download, and check
  your site's rules, because some private trackers don't allow debrid services.

**Library extras**
- *Kodi library → Back up*: Kodi's library export (with watched marks) plus its database file, saved on the library drive
  (`_Kodi library backups`) and the phone if you use one. The daily backup is skipped when nothing in the library has changed. It warns you if the library suddenly shrinks. *Restore a backup* gets one
  ready for Kodi's Import library.
- *Clean TV library / Clean movie library*: removes entries that are in the wrong library, never files.
- *Find missing episodes*: compares your TV library with TVmaze and lists aired episodes you don't have.
- *Where to watch*: says per season whether a show is on your services, free with ads, on another subscription, or available to
  buy or rent. It uses TMDb's data and needs a free TMDb key.
- *Free up space*: shows what's using the device's storage and clears leftovers.
- *View a text / NFO file*: reads old DOS-style NFO art correctly.

---

## Version history

See [CHANGELOG.md](CHANGELOG.md), or in Kodi: **Help & settings → Version history**.

## Licence and credits

Sortovia is free software under the [MIT licence](LICENSE.txt), and comes with no warranty. It moves and deletes files when you
approve it, so keep a backup of anything you can't replace. Only use it with content you have the right to keep.

Sortovia isn't affiliated with or endorsed by Kodi or the XBMC Foundation, Microsoft, YouTube or Real-Debrid.

QR codes are drawn with the [QR Code generator library](https://www.nayuki.io/page/qr-code-generator-library) by Project Nayuki
(MIT licence), included as `qrcodegen.py`.
