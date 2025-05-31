"""
Network scanner implementation using standard sockets.
Provides host discovery and port scanning functionality without requiring privileges.
"""

import ipaddress
import socket
import concurrent.futures
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
import logging
import time
import subprocess
from ..gui.translation import _

# Import AppConfig for fallback defaults
from .config import AppConfig

try:
    from .services import ServiceInfo, COMMON_SERVICES
except ImportError:
    try:
        # Handle direct execution case
        from services import ServiceInfo, COMMON_SERVICES
    except ImportError:
        # Handle case when running from project root
        from core.services import ServiceInfo, COMMON_SERVICES


@dataclass
class ScanResult:
    """Result of a network scan operation."""

    ip: str
    hostname: str
    mac: str
    vendor: str
    services: List[ServiceInfo]
    response_time: float
    is_alive: bool


class NetworkScanner:
    """Professional network scanner using standard sockets."""

    def __init__(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        config_manager=None,
    ):
        """
        Initialize the network scanner.

        Args:
            progress_callback: Optional callback for progress updates (message, percentage)
            config_manager: Configuration manager for getting custom services
        """
        self.progress_callback = progress_callback
        self.config_manager = config_manager
        self._stop_scanning = False

        # Load configuration settings
        if config_manager:
            config = config_manager.config
            self.ping_timeout = config.ping_timeout
            self.ping_attempts = config.ping_attempts
            self.hostname_timeout = config.hostname_timeout
            self.discovery_threads = config.discovery_threads
            self.scan_timeout = config.scan_timeout
            self.scan_threads = config.scan_threads
        else:
            # Default values if no config manager
            self.ping_timeout = 2.0
            self.ping_attempts = 2
            self.hostname_timeout = 0.5
            self.discovery_threads = AppConfig.default().discovery_threads
            self.scan_timeout = AppConfig.default().scan_timeout
            self.scan_threads = AppConfig.default().scan_threads

        # Add hostname resolution cache
        self.hostname_cache = {}

        # Add vendor information cache for better performance
        self.vendor_cache = {}

        # Cache avahi availability to avoid repeated checks
        self._avahi_available = None

        self._update_progress(
            _("Scanner initialized (socket-based mode)"),
            0,
        )

        # Log available hostname resolution methods
        avahi_available = self._is_avahi_available()
        if avahi_available:
            logging.info(
                _(
                    "Avahi-resolve available - enhanced local device name resolution enabled"
                )
            )
        else:
            logging.debug(
                _("Avahi-resolve not available - using standard DNS resolution only")
            )

    def stop_scan(self) -> None:
        """Stop the current scanning operation."""
        self._stop_scanning = True

    def _update_progress(self, message: str, percentage: float) -> None:
        """Update scan progress if callback is provided."""
        if self.progress_callback:
            self.progress_callback(message, percentage)

    def get_local_network_range(self) -> str:
        """
        Automatically detect the local network range.

        Returns:
            Network range in CIDR notation (e.g., "192.168.1.0/24")
        """
        try:
            # Get default gateway
            import subprocess

            result = subprocess.run(
                ["ip", "route", "show", "default"], capture_output=True, text=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if "default via" in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            interface = parts[4]
                            # Get IP address for this interface
                            ip_result = subprocess.run(
                                ["ip", "addr", "show", interface],
                                capture_output=True,
                                text=True,
                            )
                            if ip_result.returncode == 0:
                                for ip_line in ip_result.stdout.split("\n"):
                                    if (
                                        "inet " in ip_line
                                        and "127.0.0.1" not in ip_line
                                    ):
                                        ip_info = ip_line.strip().split()[1]
                                        network = ipaddress.ip_network(
                                            ip_info, strict=False
                                        )
                                        return str(network)

            # Fallback: common private network ranges
            return "192.168.1.0/24"

        except Exception:
            return "192.168.1.0/24"

    def discover_hosts(self, network_range: str) -> List[Dict[str, str]]:
        """
        Discover live hosts on the network using multiple methods.

        Args:
            network_range: Network range to scan (e.g., "192.168.1.0/24")

        Returns:
            List of discovered hosts with IP, MAC, and vendor info
        """
        self._update_progress("Discovering hosts...", 10)
        return self._enhanced_host_discovery(network_range)

    def _ping_host(self, ip: str) -> tuple[str, bool]:
        """Ping a single host to check if it's alive with improved reliability."""
        try:
            import subprocess

            # Use a consistent, reliable ping command
            cmd = [
                "ping",
                "-c",
                "1",  # Send 1 packet
                "-W",
                str(int(self.ping_timeout)),  # Timeout in seconds
                "-q",  # Quiet mode
                ip,
            ]

            # Execute ping with proper timeout
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.ping_timeout + 5,  # Buffer for process overhead
            )

            success = result.returncode == 0
            if success:
                logging.debug(f"Ping success: {ip}")
            else:
                logging.debug(f"Ping failed: {ip} (returncode: {result.returncode})")

            return ip, success

        except subprocess.TimeoutExpired:
            logging.debug(f"Ping timeout: {ip}")
            return ip, False
        except Exception as e:
            logging.debug(f"Ping error for {ip}: {e}")
            return ip, False

    def _get_system_arp_table(self) -> Dict[str, str]:
        """Get ARP table from system using 'arp' or 'ip neigh' command."""
        arp_table = {}

        try:
            import subprocess

            # Try 'ip neigh' first (more reliable on modern systems)
            try:
                result = subprocess.run(
                    ["ip", "neigh"], capture_output=True, text=True, timeout=5
                )

                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        parts = line.split()
                        if len(parts) >= 5 and parts[1] == "dev":
                            ip = parts[0]
                            # Find MAC address in the line
                            for i, part in enumerate(parts):
                                if ":" in part and len(part) == 17:
                                    arp_table[ip] = part
                                    break

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            # Fallback to 'arp' command
            if not arp_table:
                try:
                    result = subprocess.run(
                        ["arp", "-a"], capture_output=True, text=True, timeout=5
                    )

                    if result.returncode == 0:
                        for line in result.stdout.splitlines():
                            # Parse lines like: "gateway (192.168.1.1) at aa:bb:cc:dd:ee:ff [ether] on wlan0"
                            parts = line.split()
                            if len(parts) >= 4:
                                ip_part = None
                                mac_part = None

                                for part in parts:
                                    if part.startswith("(") and part.endswith(")"):
                                        ip_part = part[1:-1]
                                    elif ":" in part and len(part) == 17:
                                        mac_part = part

                                if ip_part and mac_part:
                                    arp_table[ip_part] = mac_part

                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

        except Exception as e:
            logging.error(_("Failed to get ARP table") + f": {e}")

        return arp_table

    def _get_vendor(self, mac: str) -> str:
        """
        Get vendor information from MAC address using IEEE OUI file if available,
        fallback to internal OUI database. Results are cached for performance.

        Args:
            mac: MAC address

        Returns:
            Vendor name or "Unknown"
        """
        # Normalize MAC address for consistent caching
        normalized_mac = mac.replace(":", "").replace("-", "").upper()

        # Check cache first
        if normalized_mac in self.vendor_cache:
            return self.vendor_cache[normalized_mac]

        try:
            vendor = _("Unknown")

            # Method 1: Try IEEE OUI file if available (most accurate and fast)
            vendor = self._get_vendor_ieee_oui(mac)
            if vendor and vendor != "Unknown":
                self.vendor_cache[normalized_mac] = vendor
                return vendor

            # Cache the result (even if "Unknown" to avoid repeated lookups)
            self.vendor_cache[normalized_mac] = vendor
            return vendor

        except Exception:
            # Cache unknown result to avoid repeated failed lookups
            self.vendor_cache[normalized_mac] = "Unknown"
            return "Unknown"

    def _get_vendor_ieee_oui(self, mac: str) -> str:
        """
        Get vendor information by reading the IEEE OUI file directly.
        This is much faster than subprocess calls to arp-scan.

        Args:
            mac: MAC address to look up

        Returns:
            Vendor name or "Unknown"
        """
        try:
            # Check if IEEE OUI file exists
            oui_file_path = "/usr/share/arp-scan/ieee-oui.txt"
            if not hasattr(self, "_ieee_oui_available"):
                import os

                self._ieee_oui_available = os.path.isfile(oui_file_path)
                if self._ieee_oui_available:
                    logging.debug("IEEE OUI file found - using for vendor lookup")
                else:
                    logging.debug("IEEE OUI file not found - using internal database")

            if not self._ieee_oui_available:
                return "Unknown"

            # Extract OUI from MAC address (first 6 hex characters)
            oui = mac.replace(":", "").replace("-", "").upper()[:6]

            # Load and cache OUI database if not already loaded
            if not hasattr(self, "_oui_database"):
                self._load_ieee_oui_file(oui_file_path)

            # Look up vendor in the cached database
            return self._oui_database.get(oui, "Unknown")

        except Exception as e:
            logging.debug(f"IEEE OUI lookup failed for {mac}: {e}")
            return "Unknown"

    def _load_ieee_oui_file(self, file_path: str) -> None:
        """
        Load and parse the IEEE OUI file into memory for fast lookups.
        The file format is: OUI<tab>Vendor Name
        Example: 8C1F640F2<tab>Graphimecc Group SRL

        Args:
            file_path: Path to the IEEE OUI file
        """
        try:
            self._oui_database = {}

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Parse line - expected format: OUI<whitespace>Vendor Name
                    parts = line.split(None, 1)  # Split on any whitespace, max 2 parts

                    if len(parts) >= 2:
                        oui_hex = parts[0].strip()
                        vendor_name = parts[1].strip()

                        # Validate OUI format (should be hex characters)
                        if len(oui_hex) >= 6 and all(
                            c in "0123456789ABCDEF" for c in oui_hex.upper()
                        ):
                            # Use first 6 characters as OUI key
                            oui_key = oui_hex.upper()[:6]
                            self._oui_database[oui_key] = vendor_name

            logging.info(
                _("Loaded")
                + f" {len(self._oui_database)} "
                + _("OUI entries from IEEE database")
            )

        except Exception as e:
            logging.error(_("Failed to load IEEE OUI file") + f" {file_path}: {e}")
            # Initialize empty database to avoid repeated load attempts
            self._oui_database = {}

    def _get_hostname(self, ip: str) -> str:
        """
        Try to resolve hostname for an IP address using multiple fast methods with caching.
        Uses enhanced avahi integration for better local network device detection.

        Args:
            ip: IP address

        Returns:
            Hostname or the IP address if resolution fails
        """
        # Check cache first
        if ip in self.hostname_cache:
            return self.hostname_cache[ip]

        hostname = ip  # Default fallback

        # Method 1: Enhanced avahi resolution for local network devices
        if self._is_avahi_available():
            try:
                resolved = self._resolve_hostname_avahi(ip)
                if resolved and resolved != ip and not resolved.startswith(ip):
                    hostname = resolved
                    self.hostname_cache[ip] = hostname
                    logging.debug(
                        _("Avahi resolved") + f" {ip} " + _("to") + f" {hostname}"
                    )
                    return hostname

                # Try service discovery for additional device information
                services_info = self._discover_avahi_services(ip)
                if services_info["services"]:
                    # Use service-based hostname if available
                    for service in services_info["services"]:
                        if service["hostname"] and service["hostname"] != ip:
                            service_hostname = service["hostname"]
                            if service_hostname.endswith(".local"):
                                service_hostname = service_hostname[:-6]
                            if service_hostname and len(service_hostname) > 3:
                                hostname = service_hostname
                                self.hostname_cache[ip] = hostname
                                logging.debug(
                                    f"Avahi service discovery resolved {ip} to {hostname}"
                                )
                                return hostname

            except Exception as e:
                logging.debug(_("Avahi resolution failed for") + f" {ip}: {e}")

        # Method 2: Standard reverse DNS with configurable timeout
        try:
            # Set aggressive timeout for hostname resolution
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(self.hostname_timeout)

            resolved = socket.gethostbyaddr(ip)[0]
            if resolved and resolved != ip and not resolved.startswith(ip):
                hostname = resolved
                self.hostname_cache[ip] = hostname
                return hostname

        except (socket.herror, socket.gaierror, OSError):
            pass
        finally:
            if "old_timeout" in locals():
                socket.setdefaulttimeout(old_timeout)

        # Cache the result (even if it's just the IP) to avoid repeated lookups
        self.hostname_cache[ip] = hostname
        return hostname

    def _is_avahi_available(self) -> bool:
        """Check if avahi tools are available on the system (cached)."""
        if self._avahi_available is not None:
            return self._avahi_available

        try:
            # Check for multiple avahi tools - avahi-resolve and avahi-browse
            resolve_result = subprocess.run(
                ["which", "avahi-resolve"], capture_output=True, timeout=2, check=False
            )
            browse_result = subprocess.run(
                ["which", "avahi-browse"], capture_output=True, timeout=2, check=False
            )

            # Consider avahi available if at least avahi-resolve is present
            self._avahi_available = resolve_result.returncode == 0

            # Log additional capabilities
            if browse_result.returncode == 0:
                logging.debug("Avahi-browse available for enhanced service discovery")

        except Exception:
            self._avahi_available = False

        return self._avahi_available

    def _resolve_hostname_avahi(self, ip: str) -> Optional[str]:
        """
        Use avahi-resolve to get hostname for IP address with enhanced detection.
        This is particularly effective for local network devices with .local domains.

        Args:
            ip: IP address to resolve

        Returns:
            Resolved hostname or None if resolution fails
        """
        try:
            # Try address resolution first
            result = subprocess.run(
                ["avahi-resolve", "-a", ip],
                capture_output=True,
                text=True,
                timeout=self.hostname_timeout,
                check=False,
            )

            if result.returncode == 0 and result.stdout.strip():
                # avahi-resolve output format: "192.168.1.100	hostname.local"
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        resolved_ip, hostname = parts[0].strip(), parts[1].strip()
                        if resolved_ip == ip and hostname:
                            # Keep .local suffix for better identification but also try without
                            if hostname.endswith(".local"):
                                clean_hostname = hostname[:-6]
                                # Prefer the clean name if it's descriptive
                                if (
                                    len(clean_hostname) > 4
                                    and not clean_hostname.replace("-", "")
                                    .replace("_", "")
                                    .isdigit()
                                ):
                                    return clean_hostname
                                else:
                                    return hostname
                            return hostname

            # Try hostname-to-address resolution to find any known .local names
            # This helps catch devices that might be in avahi cache
            try:
                # First try common device naming patterns
                common_names = [
                    f"host-{ip.replace('.', '-')}.local",
                    f"device-{ip.split('.')[-1]}.local",
                    f"station-{ip.split('.')[-1]}.local",
                ]

                for name in common_names:
                    try:
                        reverse_result = subprocess.run(
                            ["avahi-resolve", "-n", name],
                            capture_output=True,
                            text=True,
                            timeout=1,
                            check=False,
                        )
                        if (
                            reverse_result.returncode == 0
                            and ip in reverse_result.stdout
                        ):
                            return name[:-6]  # Remove .local suffix
                    except:
                        continue

            except Exception:
                pass

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

        return None

    def _check_port(
        self, ip: str, port: int, protocol: str, timeout: float = 1.0
    ) -> bool:
        """
        Check if a specific port is open on a host.

        Args:
            ip: Target IP address
            port: Port number to check
            protocol: Protocol ('tcp' or 'udp')
            timeout: Connection timeout

        Returns:
            True if port is open, False otherwise
        """
        if self._stop_scanning:
            return False

        return self._check_port_socket(ip, port, protocol, timeout)

    def _check_port_socket(
        self, ip: str, port: int, protocol: str, timeout: float
    ) -> bool:
        """Check port using standard sockets (no root required)."""
        try:
            if protocol.lower() == "tcp":
                # TCP connect scan
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                sock.close()
                return result == 0

            elif protocol.lower() == "udp":
                # UDP is tricky without raw sockets, so we'll try a simple send
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.settimeout(timeout)
                    # Send empty packet and see if we get a response
                    sock.sendto(b"", (ip, port))
                    try:
                        sock.recvfrom(1024)
                        sock.close()
                        return True
                    except socket.timeout:
                        # Timeout might mean the port is open but not responding
                        sock.close()
                        return True
                    except Exception:
                        sock.close()
                        return False
                except Exception:
                    return False

        except Exception:
            return False

        return False

    def _get_device_type_hint(self, ip: str, services: List[ServiceInfo]) -> str:
        """
        Try to determine device type based on open services and patterns.
        Uses very conservative logic - only identifies clear servers and infrastructure.
        Most devices will remain unclassified (which is correct for clients).

        Args:
            ip: IP address
            services: List of detected services

        Returns:
            Device type hint or empty string for regular clients
        """
        # Don't classify localhost/loopback addresses
        if ip.startswith("127.") or ip == "::1":
            return ""

        service_ports = [service.port for service in services]

        # Check for common gateway IPs and hostnames
        is_likely_gateway = (
            ip.endswith(".1") or ip.endswith(".254") or ip.endswith(".255")
        )

        # Get hostname for additional checks
        hostname = ""
        for result in [self._get_hostname(ip)]:
            if result and result.lower() not in ["unknown", ip]:
                hostname = result.lower()
                break

        # Network Infrastructure (Routers, Firewalls) - VERY conservative
        gateway_hostnames = any(
            term in hostname
            for term in ["gateway", "router", "gw", "rt", "firewall", "fw"]
        )
        has_web_interface = any(port in service_ports for port in [80, 443])
        has_multiple_network_services = (
            len([p for p in service_ports if p in [53, 67, 123, 161]]) >= 2
        )

        if (is_likely_gateway and has_web_interface) or (
            gateway_hostnames and has_web_interface and has_multiple_network_services
        ):
            return "Router"

        # Dedicated Printers (high confidence - specific printer ports)
        printer_ports = [631, 9100, 515]  # IPP, JetDirect, LPR
        if any(port in service_ports for port in printer_ports):
            return "Printer"

        # Dedicated Database Servers (high confidence - must be clearly dedicated)
        db_ports = [3306, 5432, 27017, 6379]  # MySQL, PostgreSQL, MongoDB, Redis
        db_services = [p for p in service_ports if p in db_ports]
        if db_services:
            # Only classify if it has DB services + minimal other services (SSH, web admin)
            other_services = [
                p for p in service_ports if p not in db_ports + [22, 80, 443]
            ]
            if len(other_services) <= 1 and len(db_services) >= 1:
                return "Database Server"

        # Dedicated Mail Servers (high confidence - multiple mail protocols)
        mail_ports = [25, 110, 143, 465, 993, 995]
        mail_services = [p for p in service_ports if p in mail_ports]
        if len(mail_services) >= 2:  # Multiple mail protocols = dedicated mail server
            return "Mail Server"

        # NAS/Storage Devices (specific vendor ports)
        nas_ports = [5000, 5001, 2049, 548]  # Synology, QNAP, NFS, AFP
        if any(port in service_ports for port in nas_ports):
            return "NAS"

        # Smart TV/Media Devices (specific streaming ports)
        media_ports = [8008, 8009, 7000, 32469, 1900]  # Chromecast, Apple TV, UPnP
        if any(port in service_ports for port in media_ports):
            return "Media Device"

        # IP Cameras (specific streaming/camera protocols)
        camera_ports = [554, 8554, 1935]  # RTSP, RTMP
        if any(port in service_ports for port in camera_ports):
            return "Camera"

        # Dedicated Development Servers (clear dev environments only)
        dev_ports = [3000, 3001, 5000, 8000, 8001]
        dev_services = [p for p in service_ports if p in dev_ports]
        if dev_services and len(service_ports) <= 3:  # Only dev ports + maybe SSH/admin
            return "Dev Server"

        # **VERY CONSERVATIVE** server detection
        # Only classify as server if MULTIPLE strong server indicators

        # Count STRONG server indicators (not client services)
        strong_server_indicators = 0

        # Web server with many services (not just web admin interface)
        if any(port in service_ports for port in [80, 443]) and len(service_ports) >= 5:
            strong_server_indicators += 1

        # SSH with many services (potential Linux server)
        if 22 in service_ports and len(service_ports) >= 5:
            strong_server_indicators += 1

        # Mail services (servers, not clients)
        if any(port in service_ports for port in [25, 110, 143, 465, 993, 995]):
            strong_server_indicators += 1

        # Domain services (DC, LDAP)
        if any(port in service_ports for port in [88, 389, 636]):
            strong_server_indicators += 1

        # Only classify as server if MULTIPLE strong indicators (not just one)
        if strong_server_indicators >= 2:
            if 3389 in service_ports:  # RDP detected
                return "Windows Server"
            elif 22 in service_ports:  # Linux with SSH
                return "Linux Server"
            elif any(port in service_ports for port in [80, 443]):
                return "Web Server"

        # For EVERYTHING ELSE - return empty string
        # This includes:
        # - Workstations/laptops with SMB, NetBIOS, etc.
        # - Clients with DHCP, DNS, NTP, SNMP ports open
        # - Devices with just SSH access
        # - Devices with just web interfaces
        # - Any device that doesn't clearly provide services to the network

        return ""

    def _enhance_hostname(
        self, ip: str, hostname: str, services: List[ServiceInfo]
    ) -> str:
        """
        Enhance hostname with device type information if hostname is just an IP.

        Args:
            ip: IP address
            hostname: Original hostname
            services: Detected services

        Returns:
            Enhanced hostname
        """
        # If we got a real hostname, return it
        if hostname != ip:
            return hostname

        # Get device type hint
        device_type = self._get_device_type_hint(ip, services)
        if device_type:
            last_octet = ip.split(".")[-1]
            return f"{device_type}-{last_octet}"

        # If no device type detected, check if it's a common gateway
        if ip.endswith(".1"):
            return f"Gateway-{ip.split('.')[-1]}"

        return ip

    def scan_network(self, network_range: str) -> List[ScanResult]:
        """
        Perform a comprehensive network scan with parallel hostname and service detection.

        Args:
            network_range: Network range to scan

        Returns:
            List of scan results for all discovered hosts
        """
        # Refresh configuration values in case settings changed
        if self.config_manager:
            cfg = self.config_manager.config
            self.ping_timeout = cfg.ping_timeout
            self.ping_attempts = cfg.ping_attempts
            self.hostname_timeout = cfg.hostname_timeout
            self.discovery_threads = cfg.discovery_threads
            self.scan_timeout = cfg.scan_timeout
            self.scan_threads = cfg.scan_threads
        self._stop_scanning = False
        # Use configured scan_threads for unified port scanning
        thread_count = (
            self.config_manager.config.scan_threads
            if self.config_manager
            else self.scan_threads
        )
        results = []

        try:
            # Step 1: Discover hosts
            self._update_progress(_("Scanning network for live hosts..."), 5)
            hosts = self.discover_hosts(network_range)

            if not hosts:
                self._update_progress(_("No hosts found"), 100)
                return results

            # Step 2: Resolve hostnames for all hosts in parallel
            total_hosts = len(hosts)
            self._update_progress(_("Resolving hostnames..."), 35)

            # Resolve all hostnames in parallel
            hostname_results = {}
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(self.discovery_threads, total_hosts)
            ) as executor:
                hostname_futures = {
                    executor.submit(self._get_hostname, host["ip"]): host["ip"]
                    for host in hosts
                }

                completed = 0
                for future in concurrent.futures.as_completed(hostname_futures):
                    if self._stop_scanning:
                        break

                    ip = hostname_futures[future]
                    try:
                        hostname = future.result(timeout=self.hostname_timeout + 0.5)
                        hostname_results[ip] = hostname
                    except (concurrent.futures.TimeoutError, Exception):
                        hostname_results[ip] = ip

                    completed += 1
                    progress = 35 + (completed / total_hosts) * 20
                    self._update_progress(
                        _("Resolved") + f" {completed}/{total_hosts} " + _("hostnames"),
                        progress,
                    )

            # Step 3: Scan services for all hosts in parallel
            self._update_progress(_("Scanning services..."), 55)

            # Get all services to scan
            if self.config_manager:
                services_to_scan = self.config_manager.get_all_services()
            else:
                services_to_scan = COMMON_SERVICES

            # Create all port scan tasks (host x service combinations)
            all_scan_tasks = []
            for host in hosts:
                for service in services_to_scan:
                    all_scan_tasks.append((host["ip"], service))

            # Execute all port scans in parallel using configured scan_threads
            service_results = {host["ip"]: [] for host in hosts}
            total_scans = len(all_scan_tasks)
            # Show actual thread count from configuration
            self._update_progress(
                _("Starting port scan:")
                + f" {total_scans} "
                + _("tasks with")
                + f" {thread_count} "
                + _("threads"),
                55,
            )
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=thread_count
            ) as executor:
                # Submit all port scan tasks
                future_to_task = {
                    executor.submit(
                        self._check_port,
                        ip,
                        service.port,
                        service.protocol,
                        self.scan_timeout,
                    ): (ip, service)
                    for ip, service in all_scan_tasks
                }

                completed = 0
                for future in concurrent.futures.as_completed(future_to_task):
                    if self._stop_scanning:
                        break

                    ip, service = future_to_task[future]
                    try:
                        if future.result():
                            service_results[ip].append(service)
                    except Exception:
                        pass

                    completed += 1
                    progress = 55 + (completed / total_scans) * 30
                    if (
                        completed % 20 == 0 or completed == total_scans
                    ):  # Update less frequently
                        self._update_progress(
                            _("Scanned") + f" {completed}/{total_scans} " + _("ports"),
                            progress,
                        )

            # Step 4: Combine results
            self._update_progress(_("Finalizing results..."), 85)

            for host_data in hosts:
                if self._stop_scanning:
                    break

                ip = host_data["ip"]
                hostname = hostname_results.get(ip, ip)
                services = service_results.get(ip, [])

                # Enhance hostname with device type
                hostname = self._enhance_hostname(ip, hostname, services)

                # Create scan result
                scan_result = ScanResult(
                    ip=ip,
                    hostname=hostname,
                    mac=host_data["mac"],
                    vendor=host_data["vendor"],
                    services=services,
                    response_time=0.0,  # Not measuring individual response time anymore
                    is_alive=True,
                )
                results.append(scan_result)

            self._update_progress(_("Scan completed"), 100)
            return results

        except Exception as e:
            logging.error(f"Network scan failed: {e}")
            self._update_progress(_("Scan failed:") + f" {e}", 100)
            return results

    def _enhanced_host_discovery(self, network_range: str) -> List[Dict[str, str]]:
        """Enhanced host discovery using multiple detection methods."""
        hosts = []
        discovered_ips = set()

        try:
            # Parse IP range
            try:
                from ..utils.network import parse_ip_range
            except ImportError:
                try:
                    from utils.network import parse_ip_range
                except ImportError:
                    # Fallback: use simple IP range parsing
                    def parse_ip_range(network_range: str) -> List[str]:
                        if "/" in network_range:
                            network = ipaddress.ip_network(network_range, strict=False)
                            return [str(ip) for ip in network.hosts()]
                        elif "-" in network_range:
                            start_ip, end_ip = network_range.split("-")
                            start = ipaddress.ip_address(start_ip.strip())
                            end = ipaddress.ip_address(end_ip.strip())
                            return [
                                str(ipaddress.ip_address(int(start) + i))
                                for i in range(int(end) - int(start) + 1)
                            ]
                        else:
                            return [network_range]

            ip_list = parse_ip_range(network_range)
            if len(ip_list) > 254:
                ip_list = ip_list[:254]

            # Method 1: Optimized ping discovery
            self._update_progress(
                _("Ping scanning") + f" {len(ip_list)} " + _("addresses..."), 15
            )
            alive_hosts = []
            batch_size = 100
            max_workers = min(self.discovery_threads, 25)

            for batch_start in range(0, len(ip_list), batch_size):
                if self._stop_scanning:
                    break

                batch_ips = ip_list[batch_start : batch_start + batch_size]

                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=min(max_workers, len(batch_ips))
                ) as executor:
                    futures = [executor.submit(self._ping_host, ip) for ip in batch_ips]

                    batch_completed = 0
                    for future in concurrent.futures.as_completed(futures):
                        if self._stop_scanning:
                            break

                        try:
                            ip, is_alive = future.result(
                                timeout=self.ping_timeout * 2
                            )  # Reduced from *3 to *2
                            if is_alive:
                                alive_hosts.append(ip)
                                discovered_ips.add(ip)
                        except Exception:
                            pass

                        batch_completed += 1

                # Update progress for this batch
                completed = min(batch_start + batch_size, len(ip_list))
                progress = 15 + (completed / len(ip_list)) * 10
                self._update_progress(
                    _("Ping scan:")
                    + f" {completed}/{len(ip_list)} "
                    + _("(")
                    + f"{len(alive_hosts)} "
                    + _("found")
                    + _(")"),
                    progress,
                )

                # Only add delay for very large networks (> 200 IPs) to prevent overwhelming
                if len(ip_list) > 200 and batch_start + batch_size < len(ip_list):
                    time.sleep(0.05)  # Much shorter delay

            # Method 2: Check ARP table for recently active hosts
            self._update_progress(_("Checking ARP table..."), 26)
            arp_table = self._get_system_arp_table()
            arp_added = 0

            for ip in arp_table.keys():
                if ip not in discovered_ips and self._is_in_network(ip, network_range):
                    alive_hosts.append(ip)
                    discovered_ips.add(ip)
                    arp_added += 1

            if arp_added > 0:
                logging.debug(f"Added {arp_added} hosts from ARP table")

            # Method 3: TCP port probe for silent hosts (limited for large networks)
            self._update_progress(_("TCP port probe for silent hosts..."), 28)
            remaining_ips = [ip for ip in ip_list if ip not in discovered_ips]

            if remaining_ips:
                # Limit the number of IPs to probe for large networks
                max_probe_ips = min(50, len(remaining_ips))
                probe_ips = remaining_ips[:max_probe_ips]

                # Test fewer, more common ports to reduce load
                test_ports = [22, 80, 443, 445, 3389]  # Most common ports

                # Much smaller thread pool to avoid overwhelming the network
                max_probe_workers = min(10, len(probe_ips) * len(test_ports))

                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_probe_workers
                ) as executor:
                    port_futures = []
                    for ip in probe_ips:
                        for port in test_ports:
                            future = executor.submit(self._tcp_ping, ip, port)
                            port_futures.append((future, ip))

                    found_in_probe = set()
                    for future, ip in port_futures:
                        if self._stop_scanning:
                            break
                        try:
                            if future.result(timeout=2.0):  # Reasonable timeout
                                if (
                                    ip not in discovered_ips
                                    and ip not in found_in_probe
                                ):
                                    alive_hosts.append(ip)
                                    discovered_ips.add(ip)
                                    found_in_probe.add(ip)
                        except Exception:
                            continue

            # Build final host list with MAC and vendor info
            self._update_progress(_("Getting MAC addresses..."), 32)
            for ip in alive_hosts:
                if self._stop_scanning:
                    break

                mac = arp_table.get(ip, "")
                vendor = self._get_vendor(mac) if mac else "Unknown"
                hosts.append({"ip": ip, "mac": mac, "vendor": vendor})

            self._update_progress(_("Found") + f" {len(hosts)} " + _("hosts"), 35)
            return hosts

        except Exception as e:
            logging.error(f"Enhanced discovery failed: {e}")
            return []

    def _discover_avahi_services(self, ip: str) -> Dict[str, any]:
        """
        Use avahi-browse to discover services advertised by a device.
        This provides additional context about device types and capabilities.

        Args:
            ip: IP address to check for services

        Returns:
            Dictionary with discovered service information
        """
        services_info = {"services": [], "device_type": None, "manufacturer": None}

        if not self._is_avahi_available():
            return services_info

        try:
            # Check for avahi-browse availability
            browse_check = subprocess.run(
                ["which", "avahi-browse"], capture_output=True, timeout=1, check=False
            )
            if browse_check.returncode != 0:
                return services_info

            # Browse for all services with timeout
            result = subprocess.run(
                ["avahi-browse", "-a", "-t", "-r", "-p"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    # avahi-browse -p output format: =;eth0;IPv4;Service;_http._tcp;local;hostname;192.168.1.100;80;
                    if line.startswith("=") and ip in line:
                        parts = line.split(";")
                        if len(parts) >= 9:
                            (
                                interface,
                                protocol,
                                service_name,
                                service_type,
                                domain,
                                hostname,
                                service_ip,
                                port,
                            ) = parts[1:9]
                            if service_ip == ip:
                                service_info = {
                                    "name": service_name,
                                    "type": service_type,
                                    "port": port,
                                    "hostname": hostname,
                                }
                                services_info["services"].append(service_info)

                                # Infer device type from services
                                if (
                                    "_airplay._tcp" in service_type
                                    or "_raop._tcp" in service_type
                                ):
                                    services_info["device_type"] = "Apple Device"
                                elif "_googlecast._tcp" in service_type:
                                    services_info["device_type"] = "Chromecast Device"
                                elif (
                                    "_printer._tcp" in service_type
                                    or "_ipp._tcp" in service_type
                                ):
                                    services_info["device_type"] = "Network Printer"
                                elif (
                                    "_smb._tcp" in service_type
                                    or "_afp._tcp" in service_type
                                ):
                                    services_info["device_type"] = "File Server"
                                elif "_ssh._tcp" in service_type:
                                    services_info["device_type"] = "SSH Server"
                                elif "_http._tcp" in service_type:
                                    services_info["device_type"] = "Web Server"

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
            logging.debug(f"Avahi service discovery failed for {ip}: {e}")

        return services_info

    def _tcp_ping(self, ip: str, port: int) -> bool:
        """Perform a TCP connection test to detect hosts that don't respond to ICMP."""
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)  # Very quick timeout
            result = sock.connect_ex((ip, port))
            sock.close()
            return (
                result == 0 or result == 111
            )  # Connected or connection refused (host exists)
        except Exception:
            return False

    def _is_in_network(self, ip: str, network_range: str) -> bool:
        """Check if an IP address is within the specified network range."""
        try:
            import ipaddress

            network = ipaddress.ip_network(network_range, strict=False)
            return ipaddress.ip_address(ip) in network
        except Exception:
            return False
