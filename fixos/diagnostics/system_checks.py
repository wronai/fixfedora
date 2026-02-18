"""
Diagnostyka systemu – rozszerzona o:
- Dźwięk (ALSA, PipeWire, PulseAudio)
- Podglądy plików (thumbnails) w menedżerach plików
- Sprzęt laptopa (ACPI, sensor, touchpad, kamera)
- Ekran i grafikę
"""

from __future__ import annotations

import subprocess
import psutil
import platform
from datetime import datetime
from typing import Any

from ..platform_utils import IS_LINUX as _IS_LINUX, IS_WINDOWS as _IS_WINDOWS, IS_MAC as _IS_MAC, SYSTEM as _SYSTEM


def _cmd(cmd: str, timeout: int = 20) -> str:
    """Uruchamia komendę i zwraca output jako string."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        combined = out
        if result.returncode != 0 and err:
            combined = f"{out}\n[ERR]: {err}" if out else f"[ERR]: {err}"
        return combined or "(brak outputu)"
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT po {timeout}s]"
    except Exception as e:
        return f"[WYJĄTEK: {e}]"


# ═══════════════════════════════════════════════════════════
#  AUDIO – ALSA / PipeWire / PulseAudio / SOF
# ═══════════════════════════════════════════════════════════

def diagnose_audio() -> dict[str, Any]:
    """
    Diagnostyka dźwięku (ALSA/PipeWire/PulseAudio/SOF).
    Typowe problemy po aktualizacji system:
    - SOF (Sound Open Firmware) - brak karty dźwiękowej
    - PipeWire nie startuje / błędna konfiguracja
    - ALSA: brak urządzeń / mute
    - Intel HDA vs SOF konflikt sterowników
    """
    return {
        # System audio
        "pipewire_version": _cmd("pipewire --version 2>/dev/null | head -1"),
        "pipewire_status": _cmd("systemctl --user status pipewire.service --no-pager -l 2>/dev/null | head -20"),
        "pipewire_pulse_status": _cmd("systemctl --user status pipewire-pulse.service --no-pager -l 2>/dev/null | head -20"),
        "wireplumber_status": _cmd("systemctl --user status wireplumber.service --no-pager -l 2>/dev/null | head -20"),
        "pulseaudio_status": _cmd("systemctl --user status pulseaudio.service --no-pager 2>/dev/null | head -10"),

        # ALSA
        "alsa_cards": _cmd("cat /proc/asound/cards 2>/dev/null"),
        "alsa_devices": _cmd("aplay -l 2>/dev/null"),
        "alsa_capture": _cmd("arecord -l 2>/dev/null"),
        "alsa_mixer_controls": _cmd("amixer -c 0 scontents 2>/dev/null | head -40"),

        # PipeWire objects
        "pw_dump_audio": _cmd("pw-dump 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(n.get('info',{}).get('props',{}).get('node.name','?'), '->', n.get('info',{}).get('props',{}).get('object.path','?')) for n in d if n.get('type','') == 'PipeWire:Interface:Node']\" 2>/dev/null | head -30"),
        "pactl_info": _cmd("pactl info 2>/dev/null"),
        "pactl_sinks": _cmd("pactl list sinks 2>/dev/null | grep -E '(Name|State|Volume|Mute|Description)' | head -30"),
        "pactl_sources": _cmd("pactl list sources 2>/dev/null | grep -E '(Name|State|Volume|Mute|Description)' | head -30"),

        # Kernel / SOF (Sound Open Firmware) - kluczowy dla Lenovo/Intel
        "sof_firmware": _cmd("ls /lib/firmware/intel/sof* 2>/dev/null | head -10"),
        "sof_modules": _cmd("lsmod | grep -E '(sof|snd_hda|intel_sst|avs)' 2>/dev/null"),
        "kernel_audio_dmesg": _cmd("dmesg | grep -iE '(snd|audio|alsa|hda|sof|codec|speaker|mic|hdmi)' | tail -30"),
        "hdaudio_codec": _cmd("cat /proc/asound/card*/codec* 2>/dev/null | grep -E '(Codec|Address|Vendor)' | head -20"),

        # Lenovo-specific
        "lenovo_ideapad": _cmd("lsmod | grep -i ideapad 2>/dev/null"),
        "thinkpad_acpi": _cmd("lsmod | grep -i thinkpad_acpi 2>/dev/null"),
        "yoga_udev": _cmd("udevadm info /sys/class/sound/card0 2>/dev/null | head -20"),

        # Mikrofon
        "mic_privacy_switch": _cmd("cat /sys/bus/platform/devices/*/PNP0C14*/wmi_bus/*/mic_mute 2>/dev/null || echo 'N/A'"),
        "mic_input_mute": _cmd("amixer get Capture 2>/dev/null | tail -3"),

        # Pakiety audio
        "audio_packages": _cmd(
            "rpm -qa 2>/dev/null | grep -E '(alsa|pipewire|pulseaudio|sof-firmware|wireplumber|jack)' | sort"
        ),
        "sof_firmware_pkg": _cmd("rpm -q sof-firmware 2>/dev/null"),
        "alsa_firmware_pkg": _cmd("rpm -q alsa-firmware alsa-ucm-utils 2>/dev/null"),
    }


# ═══════════════════════════════════════════════════════════
#  THUMBNAILS – podglądy plików w menedżerach
# ═══════════════════════════════════════════════════════════

def diagnose_thumbnails() -> dict[str, Any]:
    """
    Diagnostyka podglądów plików (thumbnails) w system.
    Typowe problemy po aktualizacji:
    - Brak thumbnailerów (totem-video-thumbnailer, evince-thumbnailer)
    - Uszkodzony cache miniaturek
    - Nautilus/Thunar/Dolphin – wyłączone podglądy
    - Brak codec-ów GStreamer
    - Brakujące uprawnienia ~/.cache/thumbnails
    """
    return {
        # Desktop Environment / File manager
        "desktop_env": _cmd("echo $XDG_CURRENT_DESKTOP 2>/dev/null || echo 'nieznane'"),
        "file_manager": _cmd("ps aux 2>/dev/null | grep -E '(nautilus|thunar|dolphin|nemo|pcmanfm|caja)' | grep -v grep | awk '{print $11}' | head -3"),
        "nautilus_version": _cmd("nautilus --version 2>/dev/null"),
        "thunar_version": _cmd("thunar --version 2>/dev/null | head -1"),
        "dolphin_version": _cmd("dolphin --version 2>/dev/null | head -1"),

        # Thumbnailer binaries
        "thumbnailers_installed": _cmd("ls /usr/bin/*thumb* /usr/lib/*thumb* /usr/lib64/*thumb* 2>/dev/null"),
        "gdk_pixbuf_loaders": _cmd("gdk-pixbuf-query-loaders 2>/dev/null | grep -c 'loader' || echo '0'"),
        "thumbnailer_configs": _cmd("ls /usr/share/thumbnailers/ 2>/dev/null"),
        "local_thumbnailers": _cmd("ls ~/.local/share/thumbnailers/ 2>/dev/null"),

        # Cache stanu
        "thumbnail_cache_size": _cmd("du -sh ~/.cache/thumbnails/ 2>/dev/null || echo 'brak cache'"),
        "thumbnail_cache_count": _cmd("find ~/.cache/thumbnails/ -name '*.png' 2>/dev/null | wc -l"),
        "thumbnail_cache_perms": _cmd("ls -la ~/.cache/ 2>/dev/null | grep thumb"),
        "thumbnail_fail_files": _cmd("find ~/.cache/thumbnails/fail/ -name '*.png' 2>/dev/null | wc -l"),

        # GStreamer (podglądy wideo)
        "gst_plugins": _cmd("gst-inspect-1.0 2>/dev/null | grep -cE '(video|thumbnailer)' || echo '0 (gstreamer brak)'"),
        "gst_bad_good": _cmd("rpm -qa 2>/dev/null | grep -i 'gstreamer1-plugins' | sort"),

        # Pakiety thumbnailerów
        "thumbnailer_packages": _cmd(
            "rpm -qa 2>/dev/null | grep -iE '(thumbnailer|ffmpegthumbnailer|totem-nautilus|evince-thumbnailer|raw-thumbnailer|gnome-epub-thumbnailer)' | sort"
        ),
        "ffmpegthumbnailer": _cmd("ffmpegthumbnailer --version 2>/dev/null || echo 'ffmpegthumbnailer nie zainstalowany'"),
        "totem_thumb": _cmd("which totem-video-thumbnailer 2>/dev/null || echo 'totem-video-thumbnailer nie znaleziony'"),

        # GNOME/GTK ustawienia
        "gsettings_thumbnails": _cmd(
            "gsettings get org.gnome.nautilus.preferences show-image-thumbnails 2>/dev/null; "
            "gsettings get org.gnome.nautilus.preferences thumbnail-limit 2>/dev/null"
        ),
        "gsettings_show_previews": _cmd(
            "gsettings get org.gnome.nautilus.icon-view default-zoom-level 2>/dev/null"
        ),

        # Problemy z uprawnieniami
        "xdg_cache_dir": _cmd("echo $XDG_CACHE_HOME 2>/dev/null || echo '~/.cache (domyślnie)'"),
    }


# ═══════════════════════════════════════════════════════════
#  HARDWARE – laptop/desktop hardware diagnostics
# ═══════════════════════════════════════════════════════════

def diagnose_hardware() -> dict[str, Any]:
    """Diagnostyka sprzętu laptopa/desktopa (ACPI, kamera, touchpad, DMI)."""
    return {
        # Identyfikacja
        "dmi_product": _cmd("cat /sys/class/dmi/id/product_name 2>/dev/null"),
        "dmi_vendor": _cmd("cat /sys/class/dmi/id/sys_vendor 2>/dev/null"),
        "dmi_board": _cmd("cat /sys/class/dmi/id/board_name 2>/dev/null"),
        "bios_version": _cmd("cat /sys/class/dmi/id/bios_version 2>/dev/null"),
        "bios_date": _cmd("cat /sys/class/dmi/id/bios_date 2>/dev/null"),
        "cpu_model": _cmd("grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2 | xargs"),

        # Grafika
        "gpu_info": _cmd("lspci -nn 2>/dev/null | grep -iE '(vga|3d|display)'"),
        "drm_drivers": _cmd("ls /sys/class/drm/ 2>/dev/null"),
        "wayland_display": _cmd("echo $WAYLAND_DISPLAY $XDG_SESSION_TYPE 2>/dev/null"),

        # Touchpad / Input
        "input_devices": _cmd("cat /proc/bus/input/devices 2>/dev/null | grep -E '(Name|Handlers)' | head -20"),
        "touchpad_driver": _cmd("lsmod | grep -E '(i2c_hid|hid_multitouch|psmouse|libinput)'"),

        # Kamera
        "camera_devices": _cmd("ls /dev/video* 2>/dev/null"),
        "camera_v4l": _cmd("v4l2-ctl --list-devices 2>/dev/null | head -10"),

        # ACPI / Power
        "acpi_events": _cmd("acpi -a -b -t 2>/dev/null"),
        "battery_status": _cmd("upower -i $(upower -e | grep battery) 2>/dev/null | grep -E '(state|percentage|time|energy)'"),
        "power_profile": _cmd("powerprofilesctl get 2>/dev/null || echo 'power-profiles-daemon niedostępny'"),
        "tlp_status": _cmd("tlp-stat -s 2>/dev/null | head -5 || echo 'TLP nie zainstalowany'"),

        # Czujniki temperatury
        "sensors": _cmd("sensors 2>/dev/null || echo 'lm_sensors niedostępny (dnf install lm_sensors)'"),
    }


# ═══════════════════════════════════════════════════════════
#  SYSTEM – podstawowe metryki (psutil + komendy)
# ═══════════════════════════════════════════════════════════

def diagnose_system() -> dict[str, Any]:
    """System metrics – cross-platform: CPU, RAM, disks, processes."""
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    disks = {}
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
            disks[p.mountpoint] = {
                "device": p.device, "fstype": p.fstype,
                "total_gb": round(u.total / 1024**3, 2),
                "used_gb": round(u.used / 1024**3, 2),
                "free_gb": round(u.free / 1024**3, 2),
                "percent": u.percent,
            }
        except PermissionError:
            pass

    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x.get("cpu_percent", 0), reverse=True)

    if _IS_LINUX:
        os_release = _cmd("cat /etc/os-release | grep -E '^(NAME|VERSION|ID)='")
        kernel = _cmd("uname -r")
        uptime = _cmd("uptime -p")
    elif _IS_WINDOWS:
        os_release = _cmd('powershell -Command "(Get-WmiObject Win32_OperatingSystem).Caption"')
        kernel = _cmd('powershell -Command "(Get-WmiObject Win32_OperatingSystem).Version"')
        uptime = _cmd('powershell -Command "((Get-Date)-(gcim Win32_OperatingSystem).LastBootUpTime).ToString()"')
    else:
        os_release = _cmd("sw_vers 2>/dev/null")
        kernel = _cmd("uname -r")
        uptime = _cmd("uptime 2>/dev/null")

    result: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "platform": platform.platform(),
        "os": _SYSTEM,
        "kernel": kernel,
        "os_release": os_release,
        "uptime": uptime,
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_count": psutil.cpu_count(),
        "ram_total_gb": round(vm.total / 1024**3, 2),
        "ram_used_percent": vm.percent,
        "swap_used_percent": sw.percent,
        "disks": disks,
        "top_processes": procs[:8],
    }

    if _IS_LINUX or _IS_MAC:
        try:
            result["load_avg"] = list(psutil.getloadavg())
        except AttributeError:
            pass

    if _IS_LINUX:
        result.update({
            "updates_pending": _cmd(
                "dnf check-update -q 2>/dev/null | grep -c '^[A-Za-z]' || "
                "apt list --upgradable 2>/dev/null | grep -c upgradable || echo '0'"
            ),
            "pkg_history": _cmd("dnf history list --last=5 2>/dev/null || true"),
            "systemctl_failed": _cmd("systemctl --failed --no-legend 2>/dev/null"),
            "journal_errors_24h": _cmd("journalctl -p err -n 20 --no-pager --since '24 hours ago' 2>/dev/null"),
            "dmesg_errors": _cmd("dmesg --level=err,crit,emerg --notime 2>/dev/null | tail -15"),
            "selinux": _cmd("getenforce 2>/dev/null || echo 'N/A'"),
            "firewall": _cmd("firewall-cmd --state 2>/dev/null || echo 'N/A'"),
        })
    elif _IS_WINDOWS:
        result.update({
            "updates_pending": _cmd('powershell -Command "(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search(\"IsInstalled=0\").Updates.Count" 2>nul || echo "N/A"'),
            "services_failed": _cmd('powershell -Command "Get-Service | Where-Object{$_.Status -eq \"Stopped\" -and $_.StartType -eq \"Automatic\"} | Select-Object Name | Format-List"'),
            "event_errors": _cmd('powershell -Command "Get-EventLog -LogName System -EntryType Error -Newest 10 2>$null | Select-Object TimeGenerated,Source,Message | Format-List"'),
            "firewall": _cmd("netsh advfirewall show allprofiles state 2>nul"),
        })
    elif _IS_MAC:
        result.update({
            "updates_pending": _cmd("softwareupdate -l 2>/dev/null | grep -c '\\*' || echo '0'"),
            "launchd_failed": _cmd("launchctl list 2>/dev/null | grep -v '^-' | awk '$1 != 0 {print}' | head -10"),
            "firewall": _cmd("defaults read /Library/Preferences/com.apple.alf globalstate 2>/dev/null"),
        })

    return result


# ═══════════════════════════════════════════════════════════
#  SECURITY – bezpieczeństwo sieci i systemu
# ═══════════════════════════════════════════════════════════

def diagnose_security() -> dict[str, Any]:
    """
    Diagnostyka bezpieczeństwa systemu i sieci.
    Sprawdza: firewall, otwarte porty, usługi sieciowe, SELinux/AppArmor,
    aktualizacje bezpieczeństwa, nieautoryzowane procesy, SSH config.
    """
    result: dict[str, Any] = {}

    if _IS_LINUX:
        result.update({
            # Firewall
            "firewall_state": _cmd("firewall-cmd --state 2>/dev/null || ufw status 2>/dev/null || iptables -L -n --line-numbers 2>/dev/null | head -20 || echo 'N/A'"),
            "firewall_zones": _cmd("firewall-cmd --list-all 2>/dev/null | head -20 || ufw status verbose 2>/dev/null | head -20 || echo 'N/A'"),

            # Otwarte porty i połączenia
            "open_ports": _cmd("ss -tlnp 2>/dev/null | head -30 || netstat -tlnp 2>/dev/null | head -30"),
            "active_connections": _cmd("ss -tnp 2>/dev/null | grep ESTAB | head -20"),
            "listening_services": _cmd("ss -tlnp 2>/dev/null | awk 'NR>1 {print $1, $4, $6}' | head -20"),

            # SELinux / AppArmor
            "selinux_status": _cmd("getenforce 2>/dev/null || sestatus 2>/dev/null | head -5 || echo 'N/A'"),
            "apparmor_status": _cmd("aa-status 2>/dev/null | head -10 || apparmor_status 2>/dev/null | head -10 || echo 'N/A'"),
            "selinux_denials": _cmd("ausearch -m avc -ts recent 2>/dev/null | tail -10 || journalctl -t audit --no-pager -n 10 2>/dev/null | grep 'denied' | tail -10 || echo 'N/A'"),

            # SSH
            "ssh_config": _cmd("grep -E '^(PermitRootLogin|PasswordAuthentication|PubkeyAuthentication|Port|AllowUsers)' /etc/ssh/sshd_config 2>/dev/null || echo 'N/A'"),
            "ssh_service": _cmd("systemctl is-active sshd 2>/dev/null || systemctl is-active ssh 2>/dev/null || echo 'N/A'"),
            "ssh_authorized_keys": _cmd("find /home -name 'authorized_keys' 2>/dev/null | head -5 || echo 'N/A'"),

            # Aktualizacje bezpieczeństwa
            "security_updates": _cmd(
                "dnf updateinfo list security 2>/dev/null | wc -l || "
                "apt list --upgradable 2>/dev/null | grep -i security | wc -l || echo '0'"
            ),
            "last_security_update": _cmd(
                "dnf history list 2>/dev/null | grep -i security | head -3 || "
                "grep 'security' /var/log/dpkg.log 2>/dev/null | tail -3 || echo 'N/A'"
            ),

            # Użytkownicy i uprawnienia
            "sudo_users": _cmd("getent group sudo wheel 2>/dev/null | head -5"),
            "users_with_shell": _cmd("awk -F: '$7 !~ /nologin|false/ {print $1, $7}' /etc/passwd 2>/dev/null | head -10"),
            "suid_files": _cmd("find /usr/bin /usr/sbin /bin /sbin -perm -4000 2>/dev/null | head -15"),
            "world_writable": _cmd("find /tmp /var/tmp -world-writable -not -sticky 2>/dev/null | head -10 || echo 'N/A'"),

            # Sieć
            "network_interfaces": _cmd("ip addr show 2>/dev/null | grep -E '(^[0-9]+:|inet )' | head -20"),
            "routing_table": _cmd("ip route 2>/dev/null | head -10"),
            "dns_config": _cmd("cat /etc/resolv.conf 2>/dev/null | grep -v '^#' | head -5"),
            "hosts_file": _cmd("cat /etc/hosts 2>/dev/null | grep -v '^#' | grep -v '^$' | head -10"),

            # Procesy sieciowe
            "network_processes": _cmd("ss -tlnp 2>/dev/null | grep -v '127.0.0.1\\|::1' | awk 'NR>1 {print $4, $6}' | head -15"),
            "suspicious_connections": _cmd("ss -tnp 2>/dev/null | grep -v '127.0.0.1\\|::1\\|LISTEN' | grep ESTAB | head -10"),

            # Fail2ban / intrusion detection
            "fail2ban": _cmd("fail2ban-client status 2>/dev/null | head -5 || echo 'fail2ban nie zainstalowany'"),
            "auth_failures": _cmd("journalctl -u sshd --no-pager -n 20 2>/dev/null | grep -i 'failed\\|invalid' | tail -10 || grep 'Failed password' /var/log/auth.log 2>/dev/null | tail -10 || echo 'N/A'"),
        })
    elif _IS_WINDOWS:
        result.update({
            "firewall_state": _cmd('netsh advfirewall show allprofiles state 2>nul'),
            "open_ports": _cmd('netstat -an 2>nul | findstr LISTENING | head -20'),
            "windows_defender": _cmd('powershell -Command "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled" 2>nul'),
            "security_updates": _cmd('powershell -Command "(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search(\"IsInstalled=0 and Type=\'Software\' and IsHidden=0\").Updates | Where-Object {$_.AutoSelectOnWebSites} | Measure-Object | Select-Object Count" 2>nul'),
        })
    elif _IS_MAC:
        result.update({
            "firewall_state": _cmd("defaults read /Library/Preferences/com.apple.alf globalstate 2>/dev/null"),
            "open_ports": _cmd("netstat -an 2>/dev/null | grep LISTEN | head -20"),
            "gatekeeper": _cmd("spctl --status 2>/dev/null"),
            "sip_status": _cmd("csrutil status 2>/dev/null"),
        })

    return result


# ═══════════════════════════════════════════════════════════
#  RESOURCES – zasoby systemowe i procesy
# ═══════════════════════════════════════════════════════════

def diagnose_resources() -> dict[str, Any]:
    """
    Diagnostyka zasobów systemowych.
    Sprawdza: dysk (co zajmuje miejsce), pamięć (co ją żre),
    procesy startujące automatycznie, usługi w tle.
    """
    # Top procesów wg CPU i RAM
    top_cpu: list[dict] = []
    top_mem: list[dict] = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info", "status", "username"]):
        try:
            info = p.info
            info["memory_mb"] = round((info.get("memory_info") or type("", (), {"rss": 0})()).rss / 1024**2, 1)
            top_cpu.append(info)
            top_mem.append(dict(info))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    top_cpu.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)
    top_mem.sort(key=lambda x: x.get("memory_percent") or 0, reverse=True)

    result: dict[str, Any] = {
        "top_cpu_processes": [
            {"pid": p["pid"], "name": p["name"], "cpu_pct": p.get("cpu_percent", 0),
             "mem_mb": p.get("memory_mb", 0), "user": p.get("username", "?")}
            for p in top_cpu[:10]
        ],
        "top_mem_processes": [
            {"pid": p["pid"], "name": p["name"], "mem_pct": round(p.get("memory_percent") or 0, 2),
             "mem_mb": p.get("memory_mb", 0), "user": p.get("username", "?")}
            for p in top_mem[:10]
        ],
        "total_processes": len(top_cpu),
        "ram_available_gb": round(psutil.virtual_memory().available / 1024**3, 2),
        "ram_used_percent": psutil.virtual_memory().percent,
        "swap_used_percent": psutil.swap_memory().percent,
    }

    if _IS_LINUX:
        result.update({
            # Dysk – co zajmuje miejsce
            "disk_usage_top": _cmd("du -sh /var/log /var/cache /tmp /home 2>/dev/null | sort -h"),
            "disk_usage_home": _cmd("du -sh /home/*/ 2>/dev/null | sort -h | tail -10"),
            "large_files": _cmd("find / -xdev -size +100M -not -path '*/proc/*' -not -path '*/sys/*' 2>/dev/null | head -15"),
            "log_sizes": _cmd("du -sh /var/log/* 2>/dev/null | sort -h | tail -10"),
            "journal_size": _cmd("journalctl --disk-usage 2>/dev/null"),
            "old_kernels": _cmd("rpm -q kernel 2>/dev/null | sort -V | head -5 || dpkg -l 'linux-image-*' 2>/dev/null | grep '^ii' | head -5"),
            "package_cache": _cmd("du -sh /var/cache/dnf 2>/dev/null || du -sh /var/cache/apt 2>/dev/null || echo 'N/A'"),

            # Autostart – usługi startujące z systemem
            "autostart_services": _cmd("systemctl list-unit-files --type=service --state=enabled --no-legend 2>/dev/null | head -30"),
            "autostart_user": _cmd("systemctl --user list-unit-files --state=enabled --no-legend 2>/dev/null | head -20"),
            "startup_time": _cmd("systemd-analyze 2>/dev/null | head -3"),
            "slowest_services": _cmd("systemd-analyze blame 2>/dev/null | head -15"),

            # Pamięć – szczegóły
            "memory_details": _cmd("free -h 2>/dev/null"),
            "oom_events": _cmd("journalctl -k --no-pager -n 20 2>/dev/null | grep -i 'oom\\|killed process\\|out of memory' | tail -10 || echo 'Brak zdarzeń OOM'"),
            "swap_usage": _cmd("swapon --show 2>/dev/null || echo 'Brak swap'"),

            # Zasoby sieciowe
            "network_usage": _cmd("cat /proc/net/dev 2>/dev/null | awk 'NR>2 {print $1, \"RX:\", $2, \"TX:\", $10}' | head -10"),
        })
    elif _IS_WINDOWS:
        result.update({
            "disk_usage": _cmd('powershell -Command "Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free | Format-Table" 2>nul'),
            "autostart": _cmd('powershell -Command "Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location | Format-List" 2>nul'),
            "large_files": _cmd('powershell -Command "Get-ChildItem C:\\ -Recurse -ErrorAction SilentlyContinue | Where-Object {$_.Length -gt 100MB} | Select-Object FullName,Length | Sort-Object Length -Descending | Select-Object -First 10" 2>nul'),
        })
    elif _IS_MAC:
        result.update({
            "disk_usage_top": _cmd("du -sh /Library /Applications ~/Library 2>/dev/null | sort -h"),
            "large_files": _cmd("find / -xdev -size +100M 2>/dev/null | head -15"),
            "autostart": _cmd("launchctl list 2>/dev/null | head -20"),
            "startup_time": _cmd("system_profiler SPStartupItemDataType 2>/dev/null | head -20"),
        })

    return result


# ═══════════════════════════════════════════════════════════
#  GŁÓWNA FUNKCJA DIAGNOSTYKI
# ═══════════════════════════════════════════════════════════

DIAGNOSTIC_MODULES = {
    "system": ("🖥️  System (CPU/RAM/dyski/usługi)", diagnose_system),
    "audio": ("🔊 Dźwięk (ALSA/PipeWire/SOF/mikrofon)", diagnose_audio),
    "thumbnails": ("🖼️  Podglądy plików (thumbnails)", diagnose_thumbnails),
    "hardware": ("🔧 Sprzęt (kamera/touchpad/ACPI/DMI)", diagnose_hardware),
    "security": ("🔒 Bezpieczeństwo (firewall/porty/SELinux/SSH)", diagnose_security),
    "resources": ("📊 Zasoby (dysk/pamięć/procesy/autostart)", diagnose_resources),
}


def get_full_diagnostics(
    modules: list[str] | None = None,
    progress_callback=None,
) -> dict[str, Any]:
    """
    Zbiera diagnostykę z wybranych modułów.
    
    Args:
        modules: Lista modułów do uruchomienia (None = wszystkie)
        progress_callback: Funkcja (name, description) -> None do aktualizacji UI
    """
    selected = modules or list(DIAGNOSTIC_MODULES.keys())
    result = {}

    for key in selected:
        if key not in DIAGNOSTIC_MODULES:
            continue
        desc, fn = DIAGNOSTIC_MODULES[key]
        if progress_callback:
            progress_callback(key, desc)
        else:
            print(f"  → {desc}...", end="\r", flush=True)
        try:
            result[key] = fn()
        except Exception as e:
            result[key] = {"error": str(e)}

    if not progress_callback:
        print("  → Diagnostyka zakończona.  ")

    return result
