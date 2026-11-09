#!/bin/bash
# Otomatik çalıştırmayı kaldırır (dosyalara ve verilere dokunmaz).
for L in com.deadline-hatirlatici.tarama com.deadline-hatirlatici.postit; do
  launchctl bootout "gui/$(id -u)/$L" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/$L.plist"
done
echo "Otomatik çalıştırma kaldırıldı."
