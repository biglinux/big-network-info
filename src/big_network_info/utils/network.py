"""
Network utility functions.
Helper functions for network operations and IP address handling.
"""

import ipaddress
import socket
from typing import List


def parse_ip_range(ip_range: str) -> List[str]:
    """
    Parse various IP range formats and return list of IP addresses.

    Supported formats:
    - CIDR notation: 192.168.1.0/24
    - Range notation: 192.168.1.1-254
    - Single IP: 192.168.1.1

    Args:
        ip_range: IP range string

    Returns:
        List of IP addresses
    """
    ip_list = []

    try:
        if "/" in ip_range:
            # CIDR notation
            network = ipaddress.ip_network(ip_range, strict=False)
            ip_list = [str(ip) for ip in network.hosts()]

        elif "-" in ip_range:
            # Range notation (e.g., 192.168.1.1-254)
            if ip_range.count("-") == 1:
                start_ip, end_part = ip_range.split("-")
                start_ip = start_ip.strip()
                end_part = end_part.strip()

                # Parse start IP
                start_addr = ipaddress.ip_address(start_ip)

                # Check if end_part is just the last octet
                if "." not in end_part:
                    # Just the last octet (e.g., "192.168.1.1-254")
                    base_ip = ".".join(start_ip.split(".")[:-1])
                    start_octet = int(start_ip.split(".")[-1])
                    end_octet = int(end_part)

                    for i in range(start_octet, end_octet + 1):
                        ip_list.append(f"{base_ip}.{i}")
                else:
                    # Full IP range (e.g., "192.168.1.1-192.168.1.254")
                    end_addr = ipaddress.ip_address(end_part)
                    current = start_addr
                    while current <= end_addr:
                        ip_list.append(str(current))
                        current += 1
        else:
            # Single IP
            ip_addr = ipaddress.ip_address(ip_range)
            ip_list = [str(ip_addr)]

    except (ipaddress.AddressValueError, ValueError) as e:
        raise ValueError(f"Invalid IP range format: {ip_range}") from e

    return ip_list


def get_local_ips() -> List[str]:
    """
    Get all local IP addresses of the current machine.

    Returns:
        List of local IP addresses (excluding loopback)
    """
    local_ips = []

    try:
        # Get hostname and resolve to IP addresses
        hostname = socket.gethostname()

        # Method 1: Get IP by connecting to remote address (most reliable for primary IP)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Connect to a public DNS server (doesn't actually send data)
                s.connect(("8.8.8.8", 80))
                primary_ip = s.getsockname()[0]
                if primary_ip not in local_ips:
                    local_ips.append(primary_ip)
        except Exception:
            pass

        # Method 2: Get all IPs associated with hostname
        try:
            for addr_info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = addr_info[4][0]
                if ip not in local_ips and not ip.startswith("127."):
                    local_ips.append(ip)
        except Exception:
            pass

        # Method 3: Alternative method using gethostbyname_ex
        try:
            _, _, ips = socket.gethostbyname_ex(hostname)
            for ip in ips:
                if ip not in local_ips and not ip.startswith("127."):
                    local_ips.append(ip)
        except Exception:
            pass

    except Exception:
        pass

    return local_ips


def is_local_ip(ip: str) -> bool:
    """
    Check if the given IP address belongs to the local machine.

    Args:
        ip: IP address to check

    Returns:
        True if the IP is local, False otherwise
    """
    if ip.startswith("127."):
        return True

    local_ips = get_local_ips()
    return ip in local_ips
