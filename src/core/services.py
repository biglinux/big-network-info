"""
Network service definitions and port mappings.
Defines common services and their standard ports for network scanning.
"""

from typing import List, NamedTuple
from ..gui.translation import _


class ServiceInfo(NamedTuple):
    """Information about a network service."""

    name: str
    port: int
    protocol: str
    description: str
    access_method: str = ""  # How to access this service (http, ssh, smb, etc.)


# Common network services to scan for (wrap name & description in _())
COMMON_SERVICES: List[ServiceInfo] = [
    ServiceInfo("HTTP", 80, "tcp", _("Web interface"), "http"),
    ServiceInfo("HTTPS", 443, "tcp", _("Secure web interface"), "https"),
    ServiceInfo("HTTP Alt", 8080, "tcp", _("Alternative HTTP port"), "http"),
    ServiceInfo("HTTPS Alt", 8443, "tcp", _("Alternative HTTPS port"), "https"),
    ServiceInfo("FTP", 21, "tcp", _("File Transfer Protocol"), "ftp"),
    ServiceInfo("SFTP/SSH", 22, "tcp", _("Secure Shell/SFTP"), "ssh"),
    ServiceInfo("FTPS", 990, "tcp", _("FTP over SSL"), "ftp"),
    ServiceInfo("FTP Alt", 2221, "tcp", _("Alternative FTP port"), "ftp"),
    ServiceInfo("SFTP Alt", 2222, "tcp", _("Alternative SFTP/SSH port"), "ssh"),
    ServiceInfo("SMB/CIFS", 445, "tcp", _("File sharing protocol"), "smb"),
    ServiceInfo("NetBIOS", 139, "tcp", _("NetBIOS Session Service"), "smb"),
    ServiceInfo("Telnet", 23, "tcp", _("Unencrypted remote access"), ""),
    ServiceInfo("RDP", 3389, "tcp", _("Remote Desktop Protocol"), "rdp"),
    ServiceInfo("VNC", 5900, "tcp", _("Virtual Network Computing"), "vnc"),
    ServiceInfo("SMTP", 25, "tcp", _("Mail service"), ""),
    ServiceInfo("POP3", 110, "tcp", _("Mail retrieval"), ""),
    ServiceInfo("IMAP", 143, "tcp", _("Mail access"), ""),
    ServiceInfo("SMTPS", 465, "tcp", _("Secure SMTP"), ""),
    ServiceInfo("IMAPS", 993, "tcp", _("Secure IMAP"), ""),
    ServiceInfo("POP3S", 995, "tcp", _("Secure POP3"), ""),
    ServiceInfo("ADB", 5555, "tcp", _("Android Debug Bridge"), ""),
    ServiceInfo("Mobile HTTP", 8000, "tcp", _("Mobile/development server"), "http"),
    ServiceInfo("Mobile HTTPS", 8001, "tcp", _("Mobile/development HTTPS"), "https"),
    ServiceInfo("Node.js Dev", 3000, "tcp", _("Node.js development server"), "http"),
    ServiceInfo("React Dev", 3001, "tcp", _("React development server"), "http"),
    ServiceInfo("Flask Dev", 5000, "tcp", _("Flask development server"), "http"),
    ServiceInfo("Django Dev", 8080, "tcp", _("Django development server"), "http"),
    ServiceInfo("MQTT", 1883, "tcp", _("MQTT messaging protocol"), ""),
    ServiceInfo("Secure MQTT", 8883, "tcp", _("Secure MQTT (MQTTS)"), ""),
    ServiceInfo("MySQL", 3306, "tcp", _("MySQL database"), ""),
    ServiceInfo("PostgreSQL", 5432, "tcp", _("PostgreSQL database"), ""),
    ServiceInfo("MongoDB", 27017, "tcp", _("MongoDB database"), ""),
    ServiceInfo("Redis", 6379, "tcp", _("Redis cache"), ""),
]
