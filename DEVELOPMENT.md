# How Sortovia is built

Sortovia is a Python add-on for Kodi, with shell and Python helpers for an Android phone. It started as a command-line
script and grew to meet one real need: managing a large media library on an Xbox, using only a phone, with no PC available.

It was built by akaguyver with [Claude Code](https://claude.com/claude-code), an AI coding tool, as a development partner.

## Layout

| Path | What it does |
|---|---|
| `addon/script.kodisorter/default.py` | Menus, the sort and move engine, resume, self-update |
| `addon/script.kodisorter/sortlib.py` | Naming rules, with no Kodi dependency, shared with `kodi_sort.py` |
| `addon/script.kodisorter/` (other modules) | Backups, comics, NFO files, languages, TMDb, TVmaze, Real-Debrid, YouTube, first-run screens |
| `kodi_sort.py` | The command-line version: a dry run unless you pass `--go` |
| `tools/xbox_share.sh`, `tools/yt_helper.py`, `tools/phone/` | The phone's WebDAV share, its download helper and a one-line installer |
| `tools/build_kodi_repo.py`, `tools/site_index.html` | Build the Kodi repository and the web page |
| `tests/` | The test suite |

## Run the tests

```
python3 -m unittest discover -s tests
```

The tests need only Python. Kodi's modules are replaced with small fakes, and file operations run against real temporary
folders. Fakes copy behaviour seen on the real device, such as a file read that returns nothing from a path Kodi can't open.

## Problems that shaped the design

Some of the most useful lessons came from reading real logs from the device, because the Xbox doesn't behave as Kodi's API suggests.

- **Renames always fail on Xbox removable drives.** Even within one folder, `xbmcvfs.rename` fails. Every move on an Xbox is
  a chunked copy, a size check and then a delete, so the design can't depend on a temporary name followed by a rename.
- **A missing file reports size 0 instead of an error.** An early Resume treated "the size differs" as proof of a half
  copy and deleted a good file whose original had already gone. Now a size difference alone never justifies a delete, and a
  remote size of 0 is measured again before a copy is rejected.
- **The Xbox hides things Kodi normally reports.** It returns no gateway address, so the add-on finds the phone by checking its
  local network for the share's reply. Its system info says only "Windows", so the device model is read from Kodi's log.
- **Real paths can't be passed to Kodi's file functions there.** A path from `translatePath` reads as empty, so temporary files go
  through `special://` paths or the library drive.
- **A busy phone looked like a bad file.** Kodi holds many connections open, which exhausted the phone server's thread
  pool. Its size checks then timed out and came back as 0, and good copies were rejected. The server's pool and the add-on's size
  check were both fixed.

## Safety rules

- Nothing moves until the person has seen the full plan and approved it.
- An original is deleted only after its copy has been checked.
- Replaced files and leftovers are parked in folders instead of being deleted, except exact duplicates.
- A run saves its state, so it can resume after Kodi quits, and it cleans up half copies.

## Releases

Each version is packed into a zip with an MD5 checksum and served from GitHub Pages. The add-on checks for a newer version when it
opens, asks first, verifies the checksum, and then installs over itself. The tests check the built package too, including its
settings and the link on the web page that Kodi reads.

## Drive letters on the Xbox

The Xbox assigns removable drive letters by what's plugged in, so a USB stick can turn E: into D:. Kodi stores full addresses, in mixed forms (`E:/TV/...`, `E:\\Movies\...`, and URL-encoded inside artwork addresses). `drive_letter.py` confirms the files by listing folders on the new letter, because the Xbox reports a missing file as size 0. It then rewrites every text column of the video and music databases, each in one SQLite transaction, so a failure leaves the library as it was. A backup for each letter is saved under `_Kodi library backups/Drive X/`.

## Rewriting music tags

`id3write.py` rebuilds a tag as ID3v2.4 and leaves the audio bytes alone. Renames always fail on Xbox removable drives, so a file can't be swapped in atomically. `_write_checked` keeps a verified full copy beside the file until the overwritten file reads back identical. Each file's old tag is saved first, so a run can be undone. Artist splitting happens per file rather than through Kodi's global separators, so a band with `&` in its name stays whole when its name is a folder.

Kodi 21 on an Xbox has been seen to rebuild the music `path` table during a full `AudioLibrary.Scan` while songs keep their old `idPath`. The library then looks empty with the song count unchanged, so checks count songs joined to `path`. The cause isn't known yet. Folder records exist in two forms for one folder there (`...\\Album\` and `...\\Album/`).

A rescan must use the folder address Kodi already stores. Kodi on an Xbox treats `...\\\\Album\\` and `...\\\\Album/` as different folders, so scanning the other form adds every song again, and a clean can't remove them because the files exist.
