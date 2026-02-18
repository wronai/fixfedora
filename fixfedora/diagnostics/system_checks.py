"""
Diagnostyka systemu Fedora – rozszerzona o:
- Dźwięk (ALSA, PipeWire, PulseAudio) dla Lenovo Yoga
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
    Diagnostyka dźwięku dla Lenovo Yoga i innych laptopów.
    Typowe problemy po aktualizacji Fedora:
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
    Diagnostyka podglądów plików (thumbnails) w Fedora.
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
#  HARDWARE – Lenovo Yoga specyfika
# ═══════════════════════════════════════════════════════════

def diagnose_hardware() -> dict[str, Any]:
    """Diagnostyka sprzętu laptopa Lenovo Yoga."""
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
    """Metryki systemowe: CPU, RAM, dyski, sieć, procesy, Fedora-specyficzne."""
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

    return {
        "timestamp": datetime.now().isoformat(),
        "platform": platform.platform(),
        "kernel": _cmd("uname -r"),
        "os_release": _cmd("cat /etc/os-release | grep -E '^(NAME|VERSION|ID)='"),
        "uptime": _cmd("uptime -p"),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_count": psutil.cpu_count(),
        "load_avg": list(psutil.getloadavg()),
        "ram_total_gb": round(vm.total / 1024**3, 2),
        "ram_used_percent": vm.percent,
        "swap_used_percent": sw.percent,
        "disks": disks,
        "top_processes": procs[:8],
        "dnf_updates_pending": _cmd("dnf check-update -q 2>/dev/null | grep -c '^[A-Za-z]' || echo '0'"),
        "dnf_history": _cmd("dnf history list --last=5 2>/dev/null"),
        "systemctl_failed": _cmd("systemctl --failed --no-legend 2>/dev/null"),
        "journal_errors_24h": _cmd("journalctl -p err -n 20 --no-pager --since '24 hours ago' 2>/dev/null"),
        "dmesg_errors": _cmd("dmesg --level=err,crit,emerg --notime 2>/dev/null | tail -15"),
        "selinux": _cmd("getenforce 2>/dev/null || echo 'N/A'"),
        "firewall": _cmd("firewall-cmd --state 2>/dev/null || echo 'N/A'"),
    }


# ═══════════════════════════════════════════════════════════
#  GŁÓWNA FUNKCJA DIAGNOSTYKI
# ═══════════════════════════════════════════════════════════

DIAGNOSTIC_MODULES = {
    "system": ("🖥️  System (CPU/RAM/dyski/usługi)", diagnose_system),
    "audio": ("🔊 Dźwięk (ALSA/PipeWire/SOF/mikrofon)", diagnose_audio),
    "thumbnails": ("🖼️  Podglądy plików (thumbnails)", diagnose_thumbnails),
    "hardware": ("🔧 Sprzęt (Lenovo Yoga/kamera/touchpad)", diagnose_hardware),
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
