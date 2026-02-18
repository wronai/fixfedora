FROM fixos-base:latest

LABEL scenario="broken-network"
LABEL description="Symuluje uszkodzoną sieć: NetworkManager failed, DNS broken, rfkill blocked"

# Symuluj brak NetworkManager (usuń lub zablokuj)
RUN systemctl disable NetworkManager 2>/dev/null || true
RUN systemctl mask NetworkManager 2>/dev/null || true

# Symuluj broken DNS – nadpisz resolv.conf pustym
RUN echo "# broken DNS - no nameservers" > /etc/resolv.conf

# Symuluj rfkill block (plik stanu)
RUN mkdir -p /var/lib/misc && \
    echo "0 phy0 wlan Wireless LAN soft-blocked" > /var/lib/misc/rfkill-state 2>/dev/null || true

# Symuluj brak urządzenia sieciowego w /sys
RUN mkdir -p /etc/NetworkManager && \
    cat > /etc/NetworkManager/NetworkManager.conf << 'EOF'
[main]
plugins=keyfile
[logging]
level=DEBUG
EOF

# Ustaw flagi środowiska testowego
ENV SCENARIO=broken-network
ENV NETWORK_BROKEN=1
ENV DNS_BROKEN=1
ENV RFKILL_BLOCKED=1

# Skrypt weryfikacyjny
RUN cat > /usr/local/bin/verify-scenario.sh << 'EOF'
#!/bin/bash
echo "=== Weryfikacja scenariusza: broken-network ==="
echo "-- NetworkManager status:"
systemctl status NetworkManager 2>/dev/null || echo "NIEDOSTĘPNY/FAILED"
echo "-- DNS resolv.conf:"
cat /etc/resolv.conf
echo "-- rfkill list:"
rfkill list 2>/dev/null || echo "rfkill niedostępny"
echo "-- ip addr:"
ip addr show 2>/dev/null || echo "BRAK INTERFEJSÓW"
echo "=== Oczekiwany wynik: fixos wykryje problemy sieciowe ==="
EOF
RUN chmod +x /usr/local/bin/verify-scenario.sh

# Skrypt diagnostyczny symulujący dane sieciowe dla fixos
RUN cat > /usr/local/bin/simulate-network-diag.py << 'EOF'
#!/usr/bin/env python3
"""Symuluje dane diagnostyczne broken-network dla testów fixos."""
import json

diag = {
    "system": {
        "kernel": "6.8.9-300.fc40.x86_64",
        "systemctl_failed": (
            "  NetworkManager.service  loaded failed failed Network Manager\n"
            "  systemd-resolved.service  loaded failed failed Network Name Resolution"
        ),
        "journal_errors_24h": (
            "NetworkManager: Couldn't initialize supplicant interface\n"
            "systemd-resolved: Failed to start DNS stub listener\n"
            "kernel: rfkill: input handler disabled"
        ),
    },
    "network": {
        "nm_status": "Failed to connect to system bus",
        "dns_resolve": "Temporary failure in name resolution",
        "rfkill_list": "0: phy0: Wireless LAN\n\tSoft blocked: yes\n\tHard blocked: no",
        "ping_gateway": "connect: Network is unreachable",
    }
}
print(json.dumps(diag, indent=2, ensure_ascii=False))
EOF
RUN chmod +x /usr/local/bin/simulate-network-diag.py

CMD ["/bin/bash"]
