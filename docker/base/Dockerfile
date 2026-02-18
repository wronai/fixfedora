FROM fedora:40

# Podstawowe narzędzia systemowe
RUN dnf install -y \
    python3 \
    python3-pip \
    python3-psutil \
    systemd \
    procps-ng \
    util-linux \
    alsa-utils \
    pulseaudio-utils \
    pipewire \
    wireplumber \
    findutils \
    which \
    udev \
    dbus \
    lsof \
    && dnf clean all

# Zainstaluj fixfedora
WORKDIR /app
COPY . /app
RUN pip3 install -e ".[dev]" --quiet

# Ustaw env testowy (bez prawdziwego tokena – używany przez testy mock)
ENV FIXFEDORA_TEST_MODE=1
ENV LLM_PROVIDER=gemini

CMD ["/bin/bash"]
