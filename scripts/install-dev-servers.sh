#!/bin/zsh
# Keep :8000 and :3000 up across Cursor sessions and crashes.
# launchd cannot read Desktop, so it only runs a watchdog in Application
# Support. If a port is down it `open`s a .command in Terminal.app, which
# does have Desktop access and runs scripts/dev-servers.sh.
set -euo pipefail

LABEL="com.arsalaan.sourabh-bot.dev-servers"
REPO="/Users/arsalaanmohammed/Desktop/Sourabh_Bot"
SUPPORT="${HOME}/Library/Application Support/sourabh-bot"
BIN_DIR="${SUPPORT}/bin"
INSTALLED_SCRIPT="${BIN_DIR}/dev-servers.sh"
INSTALLED_WATCHDOG="${BIN_DIR}/dev-servers-watchdog.sh"
INSTALLED_COMMAND="${BIN_DIR}/dev-servers.command"
DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

mkdir -p "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs/sourabh-bot" "$BIN_DIR"

chmod +x "${REPO}/scripts/dev-servers.sh" "${REPO}/scripts/install-dev-servers.sh"
cp "${REPO}/scripts/dev-servers.sh" "$INSTALLED_SCRIPT"
chmod +x "$INSTALLED_SCRIPT"
xattr -cr "$INSTALLED_SCRIPT" 2>/dev/null || true

cat >"$INSTALLED_COMMAND" <<'EOF'
#!/bin/zsh
# Opened by launchd via /usr/bin/open so Terminal has Desktop TCC access.
exec /bin/zsh "${HOME}/Library/Application Support/sourabh-bot/bin/dev-servers.sh"
EOF
chmod +x "$INSTALLED_COMMAND"
xattr -cr "$INSTALLED_COMMAND" 2>/dev/null || true

cat >"$INSTALLED_WATCHDOG" <<EOF
#!/bin/zsh
set -uo pipefail
API="http://127.0.0.1:8000/api/health"
UI="http://127.0.0.1:3000/"
CMD="${INSTALLED_COMMAND}"
LOCK="${SUPPORT}/dev-servers.pid"
STAMP="${SUPPORT}/dev-servers.last-start"
LOG="${HOME}/Library/Logs/sourabh-bot/watchdog.log"

mkdir -p "${HOME}/Library/Logs/sourabh-bot"
code() { curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "\$1" 2>/dev/null || echo 000; }
api="\$(code "\$API")"
ui="\$(code "\$UI")"
if [[ "\$api" != "000" && "\$ui" != "000" ]]; then
  exit 0
fi
if [[ -f "\$LOCK" ]]; then
  old="\$(cat "\$LOCK" 2>/dev/null || true)"
  if [[ -n "\$old" ]] && kill -0 "\$old" 2>/dev/null; then
    exit 0
  fi
fi
now="\$(date +%s)"
if [[ -f "\$STAMP" ]]; then
  last="\$(cat "\$STAMP" 2>/dev/null || echo 0)"
  if (( now - last < 45 )); then
    exit 0
  fi
fi
echo "\$now" >"\$STAMP"
echo "\$(date '+%Y-%m-%d %H:%M:%S %Z') ports api=\$api ui=\$ui — opening Terminal supervisor" >>"\$LOG"
/usr/bin/open -g "\$CMD"
EOF
chmod +x "$INSTALLED_WATCHDOG"
xattr -cr "$INSTALLED_WATCHDOG" 2>/dev/null || true

cat >"$DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>Comment</key>
  <string>Keep Product OS on :8000 and :3000. Restart if a port drops.</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>${INSTALLED_WATCHDOG}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${SUPPORT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>30</integer>
  <key>LaunchOnlyOnce</key>
  <false/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>Nice</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>${HOME}/Library/Logs/sourabh-bot/watchdog.out.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/Library/Logs/sourabh-bot/watchdog.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>${HOME}</string>
    <key>TZ</key>
    <string>Asia/Kolkata</string>
    <key>PATH</key>
    <string>${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
EOF

cp "$DST" "${REPO}/scripts/${LABEL}.plist"

if launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
  launchctl bootout "${DOMAIN}/${LABEL}" || true
fi
launchctl bootstrap "$DOMAIN" "$DST"
launchctl enable "${DOMAIN}/${LABEL}"
launchctl kickstart -k "${DOMAIN}/${LABEL}" || true

echo "Loaded ${LABEL}"
echo "Watchdog every 30s: ${INSTALLED_WATCHDOG}"
echo "Supervisor: ${INSTALLED_SCRIPT}"
echo "Logs: ${HOME}/Library/Logs/sourabh-bot/{api,ui,dev-servers,watchdog}.log"
echo "Manual start: open '${INSTALLED_COMMAND}'"
echo "   or: ${REPO}/scripts/dev-servers.sh"
