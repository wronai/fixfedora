FROM fixfedora-base:latest

LABEL scenario="broken-thumbnails"
LABEL description="Symuluje brak podglądów: brak thumbnailerów, pusty cache, brak GStreamer"

# Usuń thumbnailer y
RUN dnf remove -y \
    ffmpegthumbnailer \
    totem-nautilus \
    evince-nautilus \
    gnome-epub-thumbnailer \
    raw-thumbnailer \
    gstreamer1-plugins-bad-free \
    gstreamer1-plugins-good \
    2>/dev/null || true

# Usuń konfiguracje thumbnailerów
RUN rm -rf /usr/share/thumbnailers/ && mkdir -p /usr/share/thumbnailers/

# Stwórz pusty (uszkodzony) cache thumbnails
RUN mkdir -p /root/.cache/thumbnails/{normal,large,fail/gnome-thumbnail-factory} && \
    chmod 700 /root/.cache/thumbnails

# Symuluj uszkodzone ustawienia GNOME (brak podglądów włączonych)
RUN mkdir -p /root/.config/dconf && \
    cat > /root/.config/dconf/user.d/99-thumbnails.conf << 'EOF'
[org/gnome/nautilus/preferences]
show-image-thumbnails='never'
thumbnail-limit=uint64 0
EOF

ENV SCENARIO=broken-thumbnails
ENV THUMBNAILS_BROKEN=1

RUN cat > /usr/local/bin/verify-scenario.sh << 'EOF'
#!/bin/bash
echo "=== Weryfikacja scenariusza: broken-thumbnails ==="
echo "-- Thumbnailers w /usr/share/thumbnailers/:"
ls /usr/share/thumbnailers/ 2>/dev/null || echo "PUSTY"
echo "-- ffmpegthumbnailer:"
which ffmpegthumbnailer 2>/dev/null || echo "BRAK"
echo "-- Thumbnail cache:"
find /root/.cache/thumbnails/ -name "*.png" | wc -l
echo "=== Oczekiwany wynik: fixfedora wykryje brak thumbnailerów ==="
EOF
RUN chmod +x /usr/local/bin/verify-scenario.sh

CMD ["/bin/bash"]
