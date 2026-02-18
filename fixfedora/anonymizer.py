"""
Moduł anonimizacji wrażliwych danych systemowych.
Maskuje IP, ścieżki użytkowników, hostname i nazwy użytkowników.
"""

import re
import socket
import getpass
import os


def get_sensitive_values() -> dict:
    """Zbiera aktualne wrażliwe wartości systemowe do zamaskowania."""
    sensitive = {}
    try:
        sensitive['hostname'] = socket.gethostname()
    except Exception:
        sensitive['hostname'] = None
    try:
        sensitive['username'] = getpass.getuser()
    except Exception:
        sensitive['username'] = None
    try:
        sensitive['home_dir'] = os.path.expanduser("~")
    except Exception:
        sensitive['home_dir'] = None
    return sensitive


def anonymize(data_str: str) -> str:
    """
    Anonimizuje wrażliwe dane w stringu.
    
    Maskuje:
    - Adresy IPv4 (dwa ostatnie oktety)
    - Ścieżki /home/<user>
    - Aktualny hostname
    - Aktualną nazwę użytkownika
    - Zmienne środowiskowe z hasłami/tokenami
    """
    if not isinstance(data_str, str):
        data_str = str(data_str)

    sensitive = get_sensitive_values()

    # Maskuj konkretny hostname
    if sensitive.get('hostname'):
        data_str = data_str.replace(sensitive['hostname'], '[HOSTNAME]')

    # Maskuj konkretną nazwę użytkownika
    if sensitive.get('username'):
        data_str = re.sub(
            rf'\b{re.escape(sensitive["username"])}\b',
            '[USER]',
            data_str
        )

    # Maskuj konkretny katalog domowy
    if sensitive.get('home_dir'):
        data_str = data_str.replace(sensitive['home_dir'], '/home/[USER]')

    # Maskuj adresy IPv4: zachowaj dwa pierwsze oktety, maskuj resztę
    data_str = re.sub(
        r'\b(\d{1,3}\.\d{1,3})\.\d{1,3}\.\d{1,3}\b',
        r'\1.XXX.XXX',
        data_str
    )

    # Maskuj ścieżki /home/<dowolny_user>
    data_str = re.sub(r'/home/[^\s/:"\']+', '/home/[USER]', data_str)

    # Maskuj potencjalne tokeny API / klucze (długie alfanumeryczne ciągi)
    data_str = re.sub(
        r'\b(sk-|pk-|Bearer\s+)[A-Za-z0-9\-_]{20,}\b',
        r'\1[REDACTED]',
        data_str
    )

    # Maskuj hasła w zmiennych środowiskowych
    data_str = re.sub(
        r'(?i)(password|passwd|secret|token|api_key|apikey)\s*[=:]\s*\S+',
        r'\1=[REDACTED]',
        data_str
    )

    return data_str
