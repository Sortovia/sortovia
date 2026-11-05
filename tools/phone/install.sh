#!/data/data/com.termux/files/usr/bin/bash
# Kodi Sorter phone helper - one-step install for plain Termux (no Ubuntu needed).
#
#   pkg install -y curl && curl -fsSL https://akaguyver.github.io/kodi-repo/phone/install.sh | bash
#
# Installs rclone (the Wi-Fi share), Python, yt-dlp, ffmpeg and nodejs (YouTube
# downloads), and the `xbox-share` command. Run it again any time to update.
set -e
BASE="${KS_BASE:-https://akaguyver.github.io/kodi-repo/phone}"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
DIR="$PREFIX/share/kodi-sorter"
CONF="$HOME/.config/xbox-share"
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

if [ ! -d /data/data/com.termux ] && [ -z "$KS_TEST" ]; then
  echo "This installer is for Termux on Android (from F-Droid or GitHub, not the Play Store)."; exit 1
fi

if [ -z "$KS_NO_PKG" ]; then
  say "1/4  Installing programs (a few minutes the first time)..."
  pkg update -y
  pkg install -y rclone python yt-dlp ffmpeg nodejs termux-tools
else
  say "1/4  Skipping program install (KS_NO_PKG set)"
fi

say "2/4  Storage access"
if [ -d /storage/emulated/0/Download ] && ls /storage/emulated/0/Download >/dev/null 2>&1; then
  echo "Termux can already see the phone's Download folder."
else
  echo "Android will ask to let Termux use the phone's storage - tap ALLOW."
  termux-setup-storage || true
  for i in $(seq 1 30); do ls /storage/emulated/0/Download >/dev/null 2>&1 && break; sleep 1; done
  ls /storage/emulated/0/Download >/dev/null 2>&1 || echo "Still no access to Download: run termux-setup-storage and allow it."
fi

say "3/4  Downloading the Kodi Sorter phone scripts"
mkdir -p "$DIR" "$CONF"
for f in xbox_share.sh yt_helper.py; do
  curl -fsSL "$BASE/$f?t=$(date +%s)" -o "$DIR/$f.new"
  mv "$DIR/$f.new" "$DIR/$f"
done
chmod +x "$DIR/xbox_share.sh"
cat > "$PREFIX/bin/xbox-share" <<EOF
#!$PREFIX/bin/bash
# Kodi Sorter: share the phone's Download folder with Kodi, plus YouTube downloads.
command -v termux-wake-lock >/dev/null && termux-wake-lock
exec bash "$DIR/xbox_share.sh" "\$@"
EOF
chmod +x "$PREFIX/bin/xbox-share"

# Moving over from the older Ubuntu (proot) setup: keep its password, so Kodi on the
# Xbox keeps working without typing a new one, and its YouTube cookies, queue and settings.
# proot-distro keeps Ubuntu in installed-rootfs/ubuntu or containers/ubuntu/rootfs, by version.
for OLD in "$PREFIX/var/lib/proot-distro/installed-rootfs/ubuntu/root/.config/xbox-share" \
           "$PREFIX/var/lib/proot-distro/containers/ubuntu/rootfs/root/.config/xbox-share"; do
  [ -d "$OLD" ] || continue
  for f in password youtube-cookies.txt yt-jobs.json yt-settings.json; do
    if [ -s "$OLD/$f" ] && [ ! -s "$CONF/$f" ]; then cp "$OLD/$f" "$CONF/$f"; echo "Kept your $f from the Ubuntu setup."; fi
  done
done
if [ ! -s "$CONF/password" ]; then
  # letters + digits only, so it can be typed with the Xbox controller
  tr -dc 'a-z0-9' </dev/urandom | head -c 8 >"$CONF/password"
fi
chmod 600 "$CONF"/* 2>/dev/null || true

say "4/4  Checking"
ok=1
for t in rclone python3 yt-dlp ffmpeg node; do
  if command -v $t >/dev/null; then echo "  OK       $t"; else echo "  MISSING  $t"; ok=0; fi
done
[ $ok = 1 ] || echo "Something is missing: run this installer again."

cat <<EOF

=====================================================
 Done. To use it:
   1. Connect Kodi's device to the phone's Mobile Hotspot, or put both on the same Wi-Fi.
   2. In Termux type:   xbox-share
   3. In Kodi open Kodi Sorter and choose your phone. It asks once for
      the password xbox-share shows:  $(cat "$CONF/password")
 Keep Termux open (it can be in the background) while you use it.
 YouTube downloads also need your sign-in cookies once - see
 Kodi Sorter > Search & download from YouTube > How to set up cookies.
=====================================================
EOF
