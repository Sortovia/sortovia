#!/bin/bash
# xbox-share: let Kodi Sorter on the Xbox read the phone's downloads over the
# hotspot Wi-Fi (no mobile data used). Runs a password-protected WebDAV server.
#   xbox-share                      share /storage/emulated/0/Download
#   xbox-share /storage/emulated/0/Movies   share another folder
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

if ! command -v rclone >/dev/null; then
  echo "rclone is missing: run  apt install rclone"; exit 1
fi
if [ ! -d "$DIR" ]; then
  echo "Folder not found: $DIR"; exit 1
fi

# Phone's addresses on Wi-Fi/hotspot (not mobile data or the VPN)
IPS=$(ifconfig 2>/dev/null | awk '/^[a-z]/{i=$1} /inet /{print i, $2}' \
      | grep -Ev '^(lo|rmnet|tun|dummy|ccmni|ppp)' | awk '{print $2}')

echo "================ XBOX SHARE ================"
echo " Sharing : $DIR"
echo " User    : kodi"
echo " Password: $PASS"
if [ -n "$IPS" ]; then
  for ip in $IPS; do echo " Address : $ip   (port $PORT)"; done
else
  echo " Address : none found - is the Mobile Hotspot ON?"
  echo "           (Kodi Sorter finds the phone by itself anyway)"
fi
echo
echo " On the Xbox: Kodi Sorter > Choose folders again >"
echo "   My phone over Wi-Fi - phone storage"
echo " Keep Termux open while files copy. Ctrl+C stops sharing."
echo " (The NOTICE lines below are normal - it is working.)"
echo "============================================"
exec rclone serve webdav "$DIR" --addr ":$PORT" --user kodi --pass "$PASS" \
  --dir-cache-time 5s --poll-interval 0 --log-level NOTICE
