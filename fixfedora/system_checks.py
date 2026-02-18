"""
Moduł zbierający dane diagnostyczne z systemu Fedora.
Używa psutil do metryk oraz subprocess do komend systemowych.
"""

import subprocess
import psutil
import platform
from datetime import datetime


def run_cmd(cmd: str, timeout: int = 30) -> str:
    """Uruchamia komendę shell i zwraca output. Bezpieczny fallback przy błędzie."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            output += f"\n[STDERR]: {result.stderr.strip()}"
        return output if output else "(brak outputu)"
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT po {timeout}s]"
    except Exception as e:
        return f"[BŁĄD: {e}]"


def get_cpu_info() -> dict:
    """Metryki CPU."""
    return {
        'percent': psutil.cpu_percent(interval=1),
        'count_logical': psutil.cpu_count(logical=True),
        'count_physical': psutil.cpu_count(logical=False),
        'freq_mhz': psutil.cpu_freq().current if psutil.cpu_freq() else 'N/A',
        'load_avg_1m': psutil.getloadavg()[0],
        'load_avg_5m': psutil.getloadavg()[1],
        'load_avg_15m': psutil.getloadavg()[2],
    }


def get_memory_info() -> dict:
    """Metryki RAM i SWAP."""
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return {
        'ram_total_gb': round(vm.total / 1024**3, 2),
        'ram_used_gb': round(vm.used / 1024**3, 2),
        'ram_percent': vm.percent,
        'ram_available_gb': round(vm.available / 1024**3, 2),
        'swap_total_gb': round(sw.total / 1024**3, 2),
        'swap_used_gb': round(sw.used / 1024**3, 2),
        'swap_percent': sw.percent,
    }


def get_disk_info() -> dict:
    """Metryki dysków dla wszystkich partycji."""
    disks = {}
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disks[partition.mountpoint] = {
                'device': partition.device,
                'fstype': partition.fstype,
                'total_gb': round(usage.total / 1024**3, 2),
                'used_gb': round(usage.used / 1024**3, 2),
                'free_gb': round(usage.free / 1024**3, 2),
                'percent': usage.percent,
            }
        except PermissionError:
            disks[partition.mountpoint] = {'error': 'brak dostępu'}
    return disks


def get_network_info() -> dict:
    """Statystyki sieciowe (bez wrażliwych danych - anonimizacja jest osobno)."""
    interfaces = {}
    net_if_stats = psutil.net_if_stats()
    net_io = psutil.net_io_counters(pernic=True)
    for iface, stats in net_if_stats.items():
        interfaces[iface] = {
            'is_up': stats.isup,
            'speed_mbps': stats.speed,
            'mtu': stats.mtu,
            'bytes_sent': net_io[iface].bytes_sent if iface in net_io else 0,
            'bytes_recv': net_io[iface].bytes_recv if iface in net_io else 0,
        }
    return interfaces


def get_top_processes(n: int = 10) -> list:
    """Lista TOP N procesów według zużycia CPU."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
    return processes[:n]


def get_fedora_specific() -> dict:
    """Komendy specyficzne dla Fedora: dnf, journalctl, systemctl."""
    return {
        'dnf_check_update': run_cmd('dnf check-update --quiet 2>/dev/null | head -30'),
        'dnf_history_recent': run_cmd('dnf history list --last=5 2>/dev/null'),
        'journal_errors_recent': run_cmd('journalctl -p err -n 30 --no-pager --since "24 hours ago" 2>/dev/null'),
        'journal_warnings_recent': run_cmd('journalctl -p warning -n 20 --no-pager --since "2 hours ago" 2>/dev/null'),
        'systemctl_failed': run_cmd('systemctl --failed --no-legend 2>/dev/null'),
        'selinux_status': run_cmd('getenforce 2>/dev/null || echo "SELinux niedostępny"'),
        'selinux_denials': run_cmd('ausearch -m avc --start recent 2>/dev/null | tail -10 || echo "auditd niedostępny"'),
        'rpm_verify': run_cmd('rpm -Va --nofiles --nodigest 2>/dev/null | head -20'),
        'kernel_version': run_cmd('uname -r'),
        'os_release': run_cmd('cat /etc/os-release | grep -E "^(NAME|VERSION|ID)="'),
        'dmesg_errors': run_cmd('dmesg --level=err,crit,emerg --notime 2>/dev/null | tail -20'),
        'disk_smart_summary': run_cmd('smartctl --scan 2>/dev/null | head -5 || echo "smartmontools niedostępny"'),
        'firewall_status': run_cmd('firewall-cmd --state 2>/dev/null || systemctl is-active firewalld 2>/dev/null'),
        'open_ports': run_cmd('ss -tlnp 2>/dev/null | head -20'),
        'cron_errors': run_cmd('journalctl -u crond -n 10 --no-pager 2>/dev/null'),
    }


def get_full_diagnostics() -> dict:
    """
    Zbiera kompletne dane diagnostyczne systemu Fedora.
    Zwraca słownik gotowy do anonimizacji i wysłania do LLM.
    """
    print("  → CPU i obciążenie...", end="\r")
    cpu = get_cpu_info()
    print("  → Pamięć RAM i SWAP...", end="\r")
    memory = get_memory_info()
    print("  → Dyski i partycje...", end="\r")
    disks = get_disk_info()
    print("  → Sieć...            ", end="\r")
    network = get_network_info()
    print("  → Procesy...         ", end="\r")
    processes = get_top_processes()
    print("  → Fedora (dnf/systemd/journal)...", end="\r")
    fedora = get_fedora_specific()
    print("  → Gotowe!             ")

    return {
        'timestamp': datetime.now().isoformat(),
        'platform': platform.platform(),
        'cpu': cpu,
        'memory': memory,
        'disks': disks,
        'network': network,
        'top_processes': processes,
        'fedora': fedora,
    }
