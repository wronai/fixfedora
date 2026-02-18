FROM fixfedora-base:latest

LABEL scenario="broken-audio"
LABEL description="Symuluje uszkodzony dźwięk: brak sof-firmware, failed PipeWire, mute ALSA"

# Usuń firmware i biblioteki audio – symuluje brak sterownika SOF
RUN dnf remove -y sof-firmware alsa-firmware 2>/dev/null || true
RUN rm -f /lib/firmware/intel/sof* 2>/dev/null || true

# Symuluj brak kart ALSA
RUN mkdir -p /etc/modprobe.d/ && \
    echo "blacklist snd_hda_intel" >> /etc/modprobe.d/blacklist-audio.conf && \
    echo "blacklist snd_hda_codec_realtek" >> /etc/modprobe.d/blacklist-audio.conf && \
    echo "blacklist snd_sof_intel_hda_mlink" >> /etc/modprobe.d/blacklist-audio.conf

# Symuluj brak urządzenia audio
RUN mkdir -p /proc/asound && \
    echo "--- no soundcards ---" > /proc/asound/cards 2>/dev/null || true

# Ustaw flagę środowiska testowego
ENV SCENARIO=broken-audio
ENV AUDIO_BROKEN=1

# Skrypt diagnostyczny do weryfikacji scenariusza
RUN cat > /usr/local/bin/verify-scenario.sh << 'EOF'
#!/bin/bash
echo "=== Weryfikacja scenariusza: broken-audio ==="
echo "-- Karty ALSA:"
cat /proc/asound/cards 2>/dev/null || echo "BRAK"
echo "-- SOF firmware:"
ls /lib/firmware/intel/sof* 2>/dev/null || echo "BRAK"
echo "-- PipeWire status:"
systemctl --user status pipewire 2>/dev/null || echo "NIEDOSTĘPNY"
echo "=== Oczekiwany wynik: fixfedora wykryje brak audio ==="
EOF
RUN chmod +x /usr/local/bin/verify-scenario.sh

CMD ["/bin/bash"]
