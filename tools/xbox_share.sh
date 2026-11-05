#!/usr/bin/env bash
# xbox-share: let Sortovia read the phone's downloads over the
# hotspot Wi-Fi (no mobile data used). Runs a password-protected WebDAV server.
#   xbox-share                      share /storage/emulated/0/Download
#   xbox-share /storage/emulated/0/Movies   share another folder
#   xbox-share password             just show the password (e.g. to type it into the companion app)
#   xbox-share stop                 stop a share that's running (in any Termux session)
# Stop it with Ctrl+C (or close Termux).
DIR="${1:-/storage/emulated/0/Download}"
PORT=8080
CONF="$HOME/.config/xbox-share"
mkdir -p "$CONF"
if [ ! -s "$CONF/password" ]; then
  # letters + digits only, so it can be typed with the Xbox controller
  tr -dc 'a-z0-9' </dev/urandom | head -c 8 >"$CONF/password"
fi
PASS=$(cat "$CONF/password")
if [ "$1" = "password" ] || [ "$1" = "pass" ]; then
  echo "xbox-share password: $PASS   (user name: kodi)"
  exit 0
fi
if [ "$1" = "stop" ]; then
  # only the share itself (anchored, so it can't match this script); the YouTube helper
  # keeps running, so Sortovia's YouTube downloads still work with the companion app
  if pkill -f "^rclone serve webdav" 2>/dev/null; then
    echo "xbox-share stopped. (The companion app can share now.)"
  else
    echo "xbox-share wasn't running."
  fi
  exit 0
fi

if ! command -v rclone >/dev/null; then
  echo "rclone is missing: in Termux run  pkg install rclone  (or run the Sortovia installer again)"; exit 1
fi
if [ ! -d "$DIR" ]; then
  echo "Folder not found: $DIR"; exit 1
fi

# Phone's addresses on Wi-Fi/hotspot (not mobile data or the VPN)
IPS=$(ifconfig 2>/dev/null | awk '/^[a-z]/{i=$1} /inet /{print i, $2}' \
      | grep -Ev '^(lo|rmnet|tun|dummy|ccmni|ppp)' | awk '{print $2}')

echo "=========== KODI SORTER PHONE SHARE ========"
echo " Sharing : $DIR"
echo " User    : kodi"
echo " Password: $PASS"
if [ -n "$IPS" ]; then
  for ip in $IPS; do echo " Address : $ip   (port $PORT)"; done
else
  echo " Address : none found - is the Mobile Hotspot ON?"
  echo "           (Sortovia finds the phone by itself anyway)"
fi
echo
echo " In Kodi: Sortovia > Sort my downloads > Choose folders >"
echo "   My phone over Wi-Fi - phone storage"
echo " Keep Termux open while files copy. Ctrl+C stops sharing."
echo " YouTube downloads: Sortovia > Download from YouTube (port 8081)."
echo " (The NOTICE lines below are normal - it is working.)"
echo "============================================"
# YouTube downloads for the add-on (port 8081, same password): see yt_helper.py
HELPER="$(dirname "$(readlink -f "$0")")/yt_helper.py"
if [ -f "$HELPER" ] && [ "$DIR" = "/storage/emulated/0/Download" ]; then
  YT_SHARE="$DIR" python3 "$HELPER" &
  HPID=$!
  trap 'kill $HPID 2>/dev/null' EXIT INT TERM
fi
if (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null; then
  echo
  echo " Port $PORT is already in use: xbox-share is already running (maybe in another Termux"
  echo " session), or the companion app is sharing. Kodi can already reach the phone."
  echo " To restart it: type  xbox-share stop  then  xbox-share"
  exit 1
fi
rclone serve webdav "$DIR" --addr ":$PORT" --user kodi --pass "$PASS" \
  --dir-cache-time 5s --poll-interval 0 --log-level NOTICE
