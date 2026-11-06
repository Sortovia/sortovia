![Sortovia](https://akaguyver.github.io/kodi-repo/assets/sortovia-logo-horizontal.png)

# Sortovia

*Your library, on the right path.*

**Kodi Sorter is now called Sortovia.** Source code and bug reports: github.com/sortovia/sortovia

Sortovia is a free add-on for Kodi that turns a pile of downloads into the folders Kodi understands, so its
library recognises everything. It began as a tool for Kodi on an Xbox, with a phone as the hotspot, and it's now capable of much more.


```
E:\
├── TV\Show Name (Year)\Season 01\Show Name (Year) S01E02.mkv
├── Movies\Movie Name (Year)\Movie Name (Year).mkv
├── Comics\Series\<original file>.cbz
├── Music\Artist\Album\03 - Title.mp3
└── Tutorials\AutoCAD\<original file>.mp4
```

**You always see the plan first.** Nothing moves until you say so, and nothing is overwritten without your OK.

---

## Before you start

You need:
- **Kodi 19 or newer**, with an internet connection for the install.
- **Your files on a drive Kodi can see**, and enough free space on the drive they're going to.

That's all. A phone, a TMDb key and Real-Debrid are optional extras, and you can ignore them to begin with.

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
in **Help**.

Then:

1. Open **Downloads → Transfer and sort → Choose folders and choices**.
2. **Where are the downloads?** Pick a folder or drive.
3. **Where do they go?** Pick the drive that holds your library (for example `E:\`), or your Movies or TV folder.
4. Answer the questions about better copies, audio language, NFOs, subtitles and leftovers. If you're unsure, the first
   option is the safe one.
5. Read the preview. It lists every move, everything it will skip and why, and anything worth checking.
6. Choose **Move now**. You can run it in the background and keep using Kodi.

### Then show Kodi the new folders

Kodi only lists folders you've added as sources. Add **each folder on its own**. In Sortovia,
**Help → How to add your folders to Kodi** has the steps for your device.

| Folder | Where to add it | "This directory contains" |
|---|---|---|
| `TV` | Videos → Files → Add videos | TV shows |
| `Movies` | Videos → Files → Add videos | Movies |
| `Tutorials` | Videos → Files → Add videos | None |
| `Comics` | Pictures | (not asked) |
| `Music` | Music → Files → Add music | (not asked) |

> **Don't add a whole drive (such as `E:\`) as one source with a content type.** It overrides the folders inside it, and
> Kodi can remove your shows from the library and scan them as movies.

**On an Xbox**, Kodi's Add source browser doesn't list external drives, so type the path into the `<None>` box instead, for example:

```
win-lib://removable/E:\TV\
```

**If your drive's letter changes** (for example, plugging in or removing a USB stick turns `E:` into `D:`), your files are safe and don't need downloading again. Don't run Clean library. Instead, open **Library → Drive letter changed? Fix the library**. Sortovia checks your files really are on the new letter, saves a library backup for each letter in `_Kodi library backups`, and points Kodi's video and music libraries and Sortovia at the new letter. Then restart Kodi. Run it again whenever the letter changes.

---

## Settings

Open **Settings**.

| Setting | What it does | Starts as |
|---|---|---|
| Check for updates | Looks for a new version each time Sortovia opens | On |
| Daily library backup | Saves Kodi's library to your library drive once a day, only if the library has changed | On |
| Skip videos under 50 MB | Treats short videos as samples. Turn it off to sort short films and clips too | On |
| Rename movie titles to your language | Renames a movie named in another language. Needs a TMDb key | On |
| Use a phone as a download source | Shows the options for importing from your phone, and YouTube | Your welcome-screen answer |
| Copy logs to the phone | Saves Kodi's logs to the phone's `Download/SortoviaLogs` folder for your own records | On, once a phone is set up |
| Protect with a passcode | Encrypts your saved passwords and keys | Off |
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

## Optional: use a phone as a download source

Sortovia can import files directly from your phone over a Wi-Fi connection, and copy Kodi's logs to it. Your Kodi device and the phone
must be on the same Wi-Fi, or your Kodi device must be on the phone's hotspot. Sortovia finds the phone by itself and asks for its
password once.

| | Android app | Android Termux | iPhone |
|---|---|---|---|
| Import files from the phone | Yes | Yes | Experimental |
| Copy logs to the phone | Yes | Yes | Experimental |
| Download from YouTube | No | Yes | No |
| Setup | Install one app | Paste one command | Terminal app |

### Android: the companion app (easiest)

The Sortovia companion app sets up Kodi Share for you, with no commands to type.

1. On the phone, open **akaguyver.github.io/kodi-repo/app** and follow the steps to install it.
2. Open it and allow the **Phone settings** it asks for.
3. Tap **Start sharing**. That's all it takes to start the share, and the app shows the password.
4. In Sortovia, choose **Downloads → Transfer and sort → Choose folders and choices → My phone over Wi-Fi**, and type the password.

### Android: Termux (also gives you YouTube downloads)

1. Install **Termux** from **F-Droid** (f-droid.org/packages/com.termux). The Play Store version is outdated and doesn't work.
2. Open Termux and type this line, then tap **Allow** when Android asks about storage:

   ```
   pkg install -y curl && curl -fsSL https://akaguyver.github.io/kodi-repo/phone/install.sh | bash
   ```

   It takes a few minutes the first time. Run the same line again any time to update.
3. **To start Kodi Share,** open Termux and type:

   ```
   kodi-share
   ```

   It shows your password, then keeps running. Leave Termux open in the background while you use it.
4. In Sortovia, choose **My phone over Wi-Fi** and type the password.

To stop it, type `kodi-share stop` in Termux. To see the password again, type `kodi-share password`. Use only one share at a time:
stop `kodi-share` before using the companion app.

For a USB drive plugged into an Android phone, use the *primitive ftpd* app from F-Droid, and choose "USB drive on the phone" in Sortovia.

### iPhone: use a terminal app until there's an iOS app (experimental)

There's no iPhone app yet. These steps run the same kind of share in the free iSH terminal app. **They haven't been tested yet**,
and iSH is slow. iOS can also pause apps in the background, so keep iSH open on screen, with the screen on, while files copy.

1. Install **iSH Shell** from the App Store and open it.
2. Type these lines one at a time. The second line lets you pick a folder from the Files app, so choose the one holding your downloads:

   ```
   apk add rclone
   mount -t ios . /mnt
   ```

3. **To start Kodi Share,** type this, replacing `yourpassword` with a password you choose (letters and numbers are easiest to type on a TV):

   ```
   rclone serve webdav /mnt --addr :8080 --user kodi --pass yourpassword
   ```

4. Turn on **Personal Hotspot** and connect your Kodi device to it, or put both on the same Wi-Fi.
5. In Sortovia, choose **My phone over Wi-Fi** and type your password. Press Ctrl+C in iSH to stop.

If it doesn't work, please send a problem report so it can be fixed.

### Download from YouTube

For now, YouTube downloads need the Android Termux setup above. Only download videos you're allowed to keep: your own, or ones the
creator permits. YouTube only allows downloads from a signed-in browser, so this needs your browser's cookies.

> **Your cookies file works like a password for your Google account.** Consider using a spare account. Automated downloading
> may be against YouTube's terms, and using it is at your own risk.

**Get the cookie extension.** Use the one called **cookies.txt, version 1.0**. It's marked for Firefox on Android, and other cookie extensions may not appear after installing:

1. In Firefox on the phone, open **akaguyver.github.io/kodi-repo/phone**.
2. **Press and hold** the file link and choose **Download link**. Tapping it normally may be blocked.
3. In Firefox, go to **Settings → About Firefox** and tap the Firefox logo **5 times** to turn on the debug menu.
4. Go back to **Settings**, choose **Install extension from file**, and pick `cookies-txt.xpi` from your Download folder. It's 87 KB.
5. Go to **Extensions → cookies.txt → Settings** and turn on *Run in private browsing*.

**Export your cookies.**

1. Open a **private tab**, sign in to youtube.com, and use the extension to export the cookies for that site, in Netscape format, into **Download**.
2. Close the tab without signing out.
3. In Termux, start Kodi Share by typing `kodi-share`. If it's already running, type `kodi-share stop` first. It finds the cookies file and
   moves it out of the shared folder to keep it private.

Repeat this export if downloads start failing.

**Download.** In Sortovia, open **YouTube**. You can search or type a link, follow **Downloads**, choose the quality and result order, then choose
**Sort the finished downloads**.

---

## If something goes wrong

**"Couldn't connect" when adding the install address, or the zip isn't listed.** Check you typed `https://akaguyver.github.io/kodi-repo/`
exactly, including the `https://` and the last `/`, and that your Kodi device is online.

**The drive doesn't appear in the Add source browser (Xbox).** Type the `win-lib://removable/...` path shown above instead
of browsing.

**My shows disappeared from the library or appeared as movies.** A source probably covers the whole drive. Remove that source,
add `TV` and `Movies` separately with the right content types, and scan again. **Library → Clean the library → Movies** removes
TV episodes wrongly listed as movies. Sortovia never deletes your video files for this.

**Kodi closed in the middle of a sort.** Open Sortovia and choose **Resume**.

**Sortovia can't find the phone.** Check the share is running on the phone and that both devices are on the same Wi-Fi or
hotspot. A VPN on the phone can get in the way. If it still can't find it, type the phone's address when asked.

**A file was skipped.** The preview says why. Common reasons: it's under 50 MB (treated as a sample; you can turn that off in Settings),
it has no audio in your language, or a better copy already exists.

**The Firefox extension won't install.** Use the exact steps under *Download from YouTube*, including **Download link** and
**Install extension from file**.

**Something else.** Use **Help → Send a problem report to the developer**. Sortovia removes passwords, keys and addresses from
Kodi's log, shows you exactly what's in it, and only sends it if you agree. It goes on paste.kodi.tv, Kodi's public log site, and can include
file and folder names. Then scan the QR code with your phone to send the developer the link, which needs a free GitHub account.

---

## What it connects to

Sortovia has no accounts of its own, no ads and no analytics. It connects only to:

| Service | When | What it sends |
|---|---|---|
| GitHub | Update checks and updates | A normal web request |
| TVmaze | *Find missing episodes* | Show names |
| TMDb | Movie titles, *Where to watch*, if you add a key | Titles and your key |
| paste.kodi.tv | Only when you send a problem report | The cleaned log, after you've agreed |
| Real-Debrid | Only if you sign in | Your links and sign-in token |
| Sites whose feeds you add | When you open *My releases* | A normal web request to the address you added |
| Your phone | Only if you set one up | Files and logs, on your own network |
| YouTube | Only from the phone, if you use YouTube downloads | Your searches, links and cookies |

When the phone is set up, Sortovia looks for it by briefly checking the addresses on your local network.

**Your passwords and keys** stay on your own device, in Kodi's add-on data. To encrypt them, turn on **Settings → Protect saved
passwords and keys with a passcode**. You type the passcode once each time Kodi starts. It can't be recovered: if you forget it, you erase those
saved details and enter them again, and your files aren't affected. Without a passcode, they're stored as plain text.

---

## All the features

**Sorting and naming**
- TV episodes (`S01E02`, `1x02`, fansub `Show - 07`, double episodes) go to `TV\Show\Season NN\`.
- Movies (a title plus a year) go to `Movies\Title (Year)\`. With a TMDb key, a movie named in another
  language can be renamed to your language, including Russian titles written in Latin letters. You can turn this off in Settings.
- OVAs, specials, and opening/ending credits clips go to Season 00, which is Kodi's Specials.
- Music (`.mp3`, `.flac`, `.m4a`, `.ogg`, `.opus` and more) goes to `Music\Artist\Album\`, named from the file's tags, then its folders. Albums by several artists go under `Various Artists`, and cover art moves with the album. Songs already in folders inside an artist's folder, podcasts, audiobooks, recordings and songs with no artist are left alone. Add `Music` to Kodi under **Music → Files → Add music**.
- **Fix music tags (MP3)**, in *File*, updates tags to ID3v2.4 and gives each album one album artist and each collaboration an `ARTISTS` tag. Then Kodi shows one album, listed under each artist if **Settings → Media → Music → Show song and album artists** is on. You see every change first, and can undo it. **Set album art from folders** uses the picture in an album's folder when Kodi shows no art.
- Comics (`.cbz/.cbr/.cb7/.cbt`, plus PDFs/EPUBs inside a "Comics" or "Manga" folder) go to `Comics\Series\`.
  `.cbr` comics become `.cbz`, which Kodi opens much faster. The Comics menu also tidies an existing Comics folder and
  can turn pages for a monitor stood on its side.
- **Tutorials** go to `Tutorials\<program>\` and keep their original names. A video counts as a tutorial when its name says so
  ("tutorial", "full course", "for beginners" and similar), when it sits in a `Tutorials\<program>` folder, or when it comes
  from a YouTube download folder and names a known program. Anything else goes to `Other`.
- Subtitles go to `Subs\` next to their video, with a language tag. You can keep only the languages you choose.
- Separate audio tracks (`.mka/.ac3/.eac3/.dts`) are placed next to their video when the video has no audio in your language.
- Download-site prefixes, release tags and junk words are stripped. Names are made safe for NTFS and exFAT.

**Choosing between copies**
- Duplicates: keeps the better copy. Audio in your language wins first, then the higher resolution, then the bigger file.
  You choose whether it asks you, always replaces, or never replaces.
- Audio language check: videos with no audio in your language can be skipped, moved to a `_No <language>` folder, or deleted.
- Samples (videos named "sample", and videos under 50 MB unless you turn that off) are left alone. Tutorials are exempt from the size limit.

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
- *Library → Backups → Back up the library now*: Kodi's library export (with watched marks) plus its database file, saved on the library drive
  (`_Kodi library backups`) and your phone if you use one. Sortovia only backs up the library when changes have been made to it. It warns you if the library suddenly shrinks. *Restore a backup* gets one
  ready for Kodi's Import library.
- *Clean TV library / Clean movie library*: removes entries that are in the wrong library, never files.
- *Find missing episodes*: compares your TV library with TVmaze and lists aired episodes you don't have.
- *Where to watch*: says per season whether a show is on your services, free with ads, on another subscription, or available to
  buy or rent. It uses TMDb's data and needs a free TMDb key.
- *Free up space*: shows what's using the device's storage and clears leftovers.
- *View a text / NFO file*: reads old DOS-style NFO art correctly.

---

## Version history

In Sortovia: **Help → Version history**.

## How it's built

See the [engineering notes](DEVELOPMENT.md) for the code layout, tests and design decisions.

## Licence and credits

Sortovia is free software under the [MIT licence](LICENSE.txt), and comes with no warranty. It moves and deletes files when you
approve it, so keep a backup of anything you can't replace. Only use it with content you have the right to keep.

The Sortovia name and logo aren't covered by the MIT licence; see the licence file for details.

Sortovia isn't affiliated with or endorsed by Kodi or the XBMC Foundation, Microsoft, YouTube or Real-Debrid.

QR codes are drawn with the [QR Code generator library](https://www.nayuki.io/page/qr-code-generator-library) by Project Nayuki
(MIT licence), included as `qrcodegen.py`.
