#!/bin/zsh
# Install or refresh the launchd agent for Cursor API sync (3x/day IST).
#
# macOS TCC blocks bare launchd (/bin/zsh) from reading Desktop. We:
# 1) copy the runner off Desktop into Application Support, and
# 2) start it via /usr/bin/open on a .command so Terminal.app's Desktop
#    permission applies (repo + .env stay on Desktop).
# Prefer: ~/.local/bin/cursor-agent login (subscription). Skip CURSOR_API_KEY
# unless you intentionally want API billing.
set -euo pipefail

LABEL="com.arsalaan.sourabh-bot.daily-sync"
REPO="/Users/arsalaanmohammed/Desktop/Sourabh_Bot"
SUPPORT="${HOME}/Library/Application Support/sourabh-bot"
BIN_DIR="${SUPPORT}/bin"
INSTALLED_SCRIPT="${BIN_DIR}/daily-api-sync.sh"
INSTALLED_COMMAND="${BIN_DIR}/daily-api-sync.command"
DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

mkdir -p "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs/sourabh-bot" "${HOME}/.config/sourabh-bot" "$BIN_DIR"

chmod +x "${REPO}/scripts/daily-api-sync.sh" "${REPO}/scripts/install-daily-sync.sh"
# Full copy — a Desktop symlink/wrapper still fails TCC for launchd.
cp "${REPO}/scripts/daily-api-sync.sh" "$INSTALLED_SCRIPT"
chmod +x "$INSTALLED_SCRIPT"
xattr -cr "$INSTALLED_SCRIPT" 2>/dev/null || true

# Terminal.app entrypoint (Desktop-readable under launchd).
cat >"$INSTALLED_COMMAND" <<'EOF'
#!/bin/zsh
# Opened by launchd via /usr/bin/open so Terminal has Desktop TCC access.
exec /bin/zsh "${HOME}/Library/Application Support/sourabh-bot/bin/daily-api-sync.sh"
EOF
chmod +x "$INSTALLED_COMMAND"
xattr -cr "$INSTALLED_COMMAND" 2>/dev/null || true

cat >"$DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>Comment</key>
  <string>09:00 / 17:00 / 01:00 Asia/Kolkata: Cursor Agent CLI Jira/Cliq/git ingest for Sourabh_Bot</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/open</string>
    <string>${INSTALLED_COMMAND}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${SUPPORT}</string>
  <key>StartCalendarInterval</key>
  <array>
    <dict>
      <key>Hour</key>
      <integer>9</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>17</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>1</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>
  </array>
  <key>RunAtLoad</key>
  <false/>
  <key>LaunchOnlyOnce</key>
  <false/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>Nice</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>${HOME}/Library/Logs/sourabh-bot/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/Library/Logs/sourabh-bot/launchd.err.log</string>
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

# Keep repo template in sync for documentation / reinstalls from git.
cp "$DST" "${REPO}/scripts/${LABEL}.plist"

if launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
  launchctl bootout "${DOMAIN}/${LABEL}" || true
fi
launchctl bootstrap "$DOMAIN" "$DST"
launchctl enable "${DOMAIN}/${LABEL}"

echo "Loaded ${LABEL}"
echo "Launchd starts: /usr/bin/open ${INSTALLED_COMMAND}"
echo "Runner: ${INSTALLED_SCRIPT}"
echo "Repo stays at: ${REPO}"
echo "Auth: cursor-agent login (free / subscription) — no CURSOR_API_KEY required"
echo "Schedule (TZ=Asia/Kolkata): 09:00, 17:00, 01:00 — Mac clock can stay local."
echo "Logs: ${HOME}/Library/Logs/sourabh-bot/"
echo "Manual run: open '${INSTALLED_COMMAND}'"
echo "   or: ${REPO}/scripts/daily-api-sync.sh"
echo
echo "One-time login if needed:"
echo "  ${HOME}/.local/bin/cursor-agent login"
