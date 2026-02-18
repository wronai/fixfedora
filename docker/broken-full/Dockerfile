FROM fixos-base:latest

LABEL scenario="broken-full"
LABEL description="Pełne środowisko testowe: broken audio + thumbnails + failed usługi + brak aktualizacji"

# === Uszkodzone audio ===
RUN dnf remove -y sof-firmware alsa-firmware 2>/dev/null || true
RUN mkdir -p /etc/modprobe.d/ && \
    echo "blacklist snd_hda_intel" >> /etc/modprobe.d/blacklist-audio.conf

# === Uszkodzone thumbnails ===
RUN dnf remove -y ffmpegthumbnailer totem-nautilus 2>/dev/null || true
RUN rm -rf /usr/share/thumbnailers/ && mkdir -p /usr/share/thumbnailers/

# === Symuluj pending aktualizacje (przez fake dnf output) ===
RUN cat > /usr/local/bin/dnf-fake << 'EOF'
#!/bin/bash
if [[ "$*" == *"check-update"* ]]; then
    echo "firefox.x86_64          128.0-1.fc40  updates"
    echo "kernel.x86_64           6.9.4-200.fc40 updates"
    echo "python3.x86_64          3.12.4-1.fc40  updates"
    echo "glibc.x86_64            2.39-7.fc40    updates"
    exit 100  # dnf check-update zwraca 100 gdy są aktualizacje
fi
exec /usr/bin/dnf "$@"
EOF
RUN chmod +x /usr/local/bin/dnf-fake

# === Symuluj failed usługi (zapisz fake systemctl output) ===
RUN cat > /usr/local/bin/systemctl-fake << 'EOF'
#!/bin/bash
if [[ "$*" == *"--failed"* ]]; then
    echo "  bluetooth.service   loaded failed failed  Bluetooth service"
    echo "  NetworkManager.service loaded failed failed Network Manager"
    exit 1
fi
exec /usr/bin/systemctl "$@"
EOF
RUN chmod +x /usr/local/bin/systemctl-fake

# === Fake /proc/asound ===
RUN mkdir -p /proc/asound_fake && \
    echo "--- no soundcards ---" > /proc/asound_fake/cards

# === Zmienne środowiskowe scenariusza ===
ENV SCENARIO=broken-full
ENV AUDIO_BROKEN=1
ENV THUMBNAILS_BROKEN=1
ENV SERVICES_FAILED=1
ENV DNF_UPDATES_PENDING=4

RUN cat > /usr/local/bin/verify-scenario.sh << 'EOF'
#!/bin/bash
echo "=== Weryfikacja scenariusza: broken-full ==="
echo "Audio broken: $AUDIO_BROKEN"
echo "Thumbnails broken: $THUMBNAILS_BROKEN"
echo "Services failed: $SERVICES_FAILED"
echo "DNF updates pending: $DNF_UPDATES_PENDING"
echo "=== Ten scenariusz symuluje wiele jednoczesnych problemów ==="
EOF
RUN chmod +x /usr/local/bin/verify-scenario.sh

CMD ["/bin/bash"]
