#!/bin/bash
# Deadline Hatırlatıcı kurulumu (her Mac'te çalışır, tekrar çalıştırmak güvenlidir):
#  - Python ortamını hazırlar
#  - Claude Code aracını ve girişini kontrol eder
#  - Mac açılınca post-it'i açan ve mailleri her 10 dakikada bir tarayan servisleri kurar
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS" "$DIR/data"

say()  { printf "\033[1m%s\033[0m\n" "$*"; }
fail() { printf "\n\033[31m%s\033[0m\n" "$*"; exit 1; }

# ---- 1. Python (Tk 8.6+ olan bir python3 lazım) -------------------------------
good_python() { "$1" -c "import tkinter, sys; sys.exit(0 if tkinter.TkVersion >= 8.6 else 1)" 2>/dev/null; }

find_python() {
  local c
  for c in $(ls -d /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 2>/dev/null | sort -t. -k2 -n -r) \
           /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3)"; do
    [ -x "$c" ] && good_python "$c" && { echo "$c"; return 0; }
  done
  return 1
}

if [ ! -x "$PY" ] || ! good_python "$PY"; then
  say "Python ortamı kuruluyor..."
  BASE_PY="$(find_python)" || fail "Uygun Python bulunamadı.
python.org/downloads adresinden en yeni Python'u (macOS installer) kur, sonra bu komutu tekrar çalıştır."
  rm -rf "$DIR/.venv"
  "$BASE_PY" -m venv "$DIR/.venv"
fi
"$PY" -m pip install -q --disable-pip-version-check pyobjc-framework-Cocoa pyobjc-framework-Quartz

# ---- 2. Claude Code ------------------------------------------------------------
CLAUDE="$(cd "$DIR" && "$PY" -c 'import deadline_reminder as d; print(d.CLAUDE)')"
if ! "$CLAUDE" --version >/dev/null 2>&1; then
  fail "Claude Code bulunamadı. Terminal'de şunu çalıştır, bitince bu komutu tekrar çalıştır:
  curl -fsSL https://claude.ai/install.sh | bash"
fi
if ! "$CLAUDE" -p --help 2>/dev/null | grep -q -- "--effort"; then
  fail "Claude Code sürümün eski ($("$CLAUDE" --version)). Güncelle:  $CLAUDE update"
fi
if ! (cd "$DIR/data" && echo "sadece OK yaz" | "$CLAUDE" -p --model haiku --tools "" \
       --no-session-persistence --setting-sources "" --strict-mcp-config >/dev/null 2>&1); then
  fail "Claude hesabına giriş yapılmamış. Terminal'de şunu çalıştır, tarayıcıda izin ver,
sonra bu komutu tekrar çalıştır:
  $CLAUDE auth login"
fi
say "Claude Code hazır: $("$CLAUDE" --version)"

# ---- 3. Otomatik başlatma servisleri ------------------------------------------
LOG="$HOME/Library/Logs/deadline-hatirlatici.log"
write_plist() { # $1=label $2=script $3=ek xml
cat > "$AGENTS/$1.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$1</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$DIR/$2</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  $3
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)/$1" 2>/dev/null || true
  while launchctl list | grep -q "$1"; do sleep 1; done
  launchctl bootstrap "gui/$(id -u)" "$AGENTS/$1.plist"
}

write_plist "com.deadline-hatirlatici.tarama" "deadline_reminder.py" \
  "<key>StartInterval</key><integer>600</integer>"
write_plist "com.deadline-hatirlatici.postit" "postit.py" \
  "<key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>"

say "Kuruldu! Post-it masaüstünde açılıyor, ilk tarama arka planda başladı."
echo "macOS izin sorarsa (Belgeler klasörü, Mail) → İzin Ver."
echo "İlerleme:  tail -f \"$DIR/data/reminder.log\""
