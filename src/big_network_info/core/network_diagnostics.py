"""
Network connectivity diagnostics module.
Provides comprehensive network connectivity testing with detailed reporting.
"""

import subprocess
import socket
import requests
import netifaces
import threading
import time
import concurrent.futures
from typing import List, Callable, Optional
from dataclasses import dataclass
from enum import Enum
from ..gui.translation import _


class DiagnosticStatus(Enum):
    """Status of a diagnostic step."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class DiagnosticStep:
    """Represents a single diagnostic step."""

    name: str
    description: str
    status: DiagnosticStatus = DiagnosticStatus.PENDING
    details: str = ""
    troubleshooting_tip: str = ""
    duration_ms: int = 0


class NetworkDiagnostics:
    """Comprehensive network connectivity diagnostics."""

    def __init__(self):
        """Initialize the network diagnostics."""
        self.steps: List[DiagnosticStep] = []
        self.current_step_index = 0
        self.is_running = False
        self.progress_callback: Optional[Callable[[DiagnosticStep], None]] = None
        self.completion_callback: Optional[Callable[[List[DiagnosticStep]], None]] = (
            None
        )

    def create_diagnostic_steps(self) -> List[DiagnosticStep]:
        """Create the list of diagnostic steps."""
        return [
            DiagnosticStep(
                name=_("List Network Devices"),
                description=_("Discovering available network interfaces"),
                troubleshooting_tip=_(
                    "Ensure network hardware is properly installed and recognized by the system"
                ),
            ),
            DiagnosticStep(
                name=_("Check Interface Status"),
                description=_("Verifying network interfaces are active"),
                troubleshooting_tip=_(
                    "Enable network interfaces or check hardware connections"
                ),
            ),
            DiagnosticStep(
                name=_("Check Link Status"),
                description=_("Verifying physical/wireless connection"),
                troubleshooting_tip=_("Check cable connections or WiFi association"),
            ),
            DiagnosticStep(
                name=_("Check IP Configuration"),
                description=_("Verifying valid IP address assignment"),
                troubleshooting_tip=_(
                    "Configure static IP or check DHCP server availability"
                ),
            ),
            DiagnosticStep(
                name=_("Check Default Route"),
                description=_("Verifying default gateway configuration"),
                troubleshooting_tip=_(
                    "Configure default gateway or check router settings"
                ),
            ),
            DiagnosticStep(
                name=_("Test Gateway Connectivity"),
                description=_("Testing connectivity to default gateway"),
                troubleshooting_tip=_(
                    "Check router/gateway availability and firewall settings"
                ),
            ),
            DiagnosticStep(
                name=_("Check DNS Configuration"),
                description=_("Displaying configured DNS servers"),
                troubleshooting_tip=_(
                    "Configure valid DNS servers (e.g., 8.8.8.8, 1.1.1.1)"
                ),
            ),
            DiagnosticStep(
                name=_("Test DNS Resolution"),
                description=_("Testing domain name resolution"),
                troubleshooting_tip=_(
                    "Check DNS server configuration or use alternative DNS servers"
                ),
            ),
            DiagnosticStep(
                name=_("Check External IP"),
                description=_("Determining external IP address"),
                troubleshooting_tip=_(
                    "Check internet connectivity and firewall settings"
                ),
            ),
            DiagnosticStep(
                name=_("Test Internet Access"),
                description=_("Testing web connectivity"),
                troubleshooting_tip=_(
                    "Check firewall settings and proxy configuration"
                ),
            ),
            DiagnosticStep(
                name=_("Test Big repositories"),
                description=_("Testing connectivity to Big Linux repositories"),
                troubleshooting_tip=_(
                    "Check connectivity to Biglinux repositories"
                ),
            ),
        ]

    def run_diagnostics(
        self,
        progress_callback: Callable[[DiagnosticStep], None],
        completion_callback: Callable[[List[DiagnosticStep]], None],
    ) -> None:
        """
        Run network diagnostics in a separate thread.

        Args:
            progress_callback: Called when each step completes
            completion_callback: Called when all diagnostics complete
        """
        self.progress_callback = progress_callback
        self.completion_callback = completion_callback
        self.steps = self.create_diagnostic_steps()
        self.current_step_index = 0
        self.is_running = True

        thread = threading.Thread(target=self._run_diagnostics_thread, daemon=True)
        thread.start()

    def _run_diagnostics_thread(self) -> None:
        """Run diagnostics in background thread with parallel execution."""
        try:
            # Define diagnostic groups based on dependencies
            # Group 1: Basic network discovery (sequential)
            basic_group = [0, 1, 2]  # List devices, interface status, link status

            # Group 2: Network configuration (can run in parallel after basic)
            config_group = [3, 4]  # IP configuration, default route

            # Group 3: Connectivity tests (can run in parallel after config)
            connectivity_group = [
                5,
                6,
                7,
                8,
                9,
                10,
            ]  # Gateway, DNS config, DNS resolution, External IP, Internet

            # Run basic group sequentially
            self._run_diagnostic_group(basic_group, parallel=False)

            # Run config group in parallel
            self._run_diagnostic_group(config_group, parallel=True)

            # Run connectivity group in parallel
            self._run_diagnostic_group(connectivity_group, parallel=True)

        finally:
            self.is_running = False
            if self.completion_callback:
                self.completion_callback(self.steps)

    def _run_diagnostic_group(
        self, step_indices: List[int], parallel: bool = False
    ) -> None:
        """Run a group of diagnostic steps either in parallel or sequentially."""
        if not self.is_running:
            return

        if parallel and len(step_indices) > 1:
            # Run steps in parallel using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(step_indices)
            ) as executor:
                # Submit all tasks
                future_to_index = {}
                for i in step_indices:
                    if not self.is_running:
                        break
                    future = executor.submit(self._execute_diagnostic_step, i)
                    future_to_index[future] = i

                # Wait for completion and handle results
                for future in concurrent.futures.as_completed(future_to_index):
                    if not self.is_running:
                        break
                    step_index = future_to_index[future]
                    try:
                        future.result()  # This will re-raise any exceptions
                    except Exception as e:
                        # Handle any exceptions that occurred during execution
                        step = self.steps[step_index]
                        step.status = DiagnosticStatus.FAILED
                        step.details = _("Error during execution:") + f" {str(e)}"
                        self._notify_progress(step)
        else:
            # Run steps sequentially
            for i in step_indices:
                if not self.is_running:
                    break
                self._execute_diagnostic_step(i)
                time.sleep(0.2)  # Brief pause for visual effect

    def _execute_diagnostic_step(self, step_index: int) -> None:
        """Execute a single diagnostic step."""
        step = self.steps[step_index]

        # Mark as running
        step.status = DiagnosticStatus.RUNNING
        self._notify_progress(step)

        start_time = time.time()

        # Run the specific diagnostic test
        success = self._run_diagnostic_step(step_index)

        end_time = time.time()
        step.duration_ms = int((end_time - start_time) * 1000)

        if success:
            step.status = DiagnosticStatus.PASSED
        else:
            step.status = DiagnosticStatus.FAILED

        self._notify_progress(step)

    def _run_diagnostic_step(self, step_index: int) -> bool:
        """Run a specific diagnostic step."""
        step = self.steps[step_index]

        try:
            if step_index == 0:
                return self._test_list_network_devices()
            elif step_index == 1:
                return self._test_interface_status()
            elif step_index == 2:
                return self._test_link_status()
            elif step_index == 3:
                return self._test_ip_configuration()
            elif step_index == 4:
                return self._test_default_route()
            elif step_index == 5:
                return self._test_gateway_connectivity()
            elif step_index == 6:
                return self._check_dns_configuration()
            elif step_index == 7:
                return self._test_dns_resolution()
            elif step_index == 8:
                return self._check_external_ip()
            elif step_index == 9:
                return self._test_internet_access()
            elif step_index == 10:
                return self._test_big_repositories()
            else:
                return False

        except Exception as e:
            step.details = _("Error:") + f" {str(e)}"
            return False

    def _test_list_network_devices(self) -> bool:
        """Test listing network devices."""
        step = self.steps[0]
        try:
            interfaces = netifaces.interfaces()
            # Filter out loopback and irrelevant interfaces
            valid_interfaces = [
                iface
                for iface in interfaces
                if not iface.startswith(("lo", "docker", "br-", "veth"))
            ]

            if valid_interfaces:
                step.details = (
                    _("Found")
                    + f" {len(valid_interfaces)} "
                    + _("network interfaces")
                    + f": {', '.join(valid_interfaces)}"
                )
                return True
            else:
                step.details = _("No valid network interfaces found")
                return False

        except Exception as e:
            step.details = _("Failed to list network interfaces") + f": {str(e)}"
            return False

    def _test_interface_status(self) -> bool:
        """Test if network interfaces are up."""
        step = self.steps[1]
        try:
            interfaces = netifaces.interfaces()
            active_interfaces = []

            for iface in interfaces:
                if iface.startswith(("lo", "docker", "br-", "veth")):
                    continue

                try:
                    # Check if interface is up using ip command
                    result = subprocess.run(
                        ["ip", "link", "show", iface],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if "state UP" in result.stdout:
                        active_interfaces.append(iface)
                except:
                    continue

            if active_interfaces:
                step.details = (
                    _("Active interfaces:") + " " + ", ".join(active_interfaces)
                )
                return True
            else:
                step.details = _("No active network interfaces found")
                return False

        except Exception as e:
            step.details = _("Failed to check interface status") + f": {str(e)}"
            return False

    def _test_link_status(self) -> bool:
        """Test physical/wireless link status."""
        step = self.steps[2]
        try:
            connected_interfaces = []

            # Check for connected interfaces
            interfaces = netifaces.interfaces()
            for iface in interfaces:
                if iface.startswith(("lo", "docker", "br-", "veth")):
                    continue

                try:
                    # Check carrier status
                    result = subprocess.run(
                        ["cat", f"/sys/class/net/{iface}/carrier"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    if result.stdout.strip() == "1":
                        connected_interfaces.append(iface)
                except:
                    continue

            if connected_interfaces:
                step.details = (
                    _("Connected interfaces:") + " " + ", ".join(connected_interfaces)
                )
                return True
            else:
                step.details = _("No connected network interfaces found")
                return False

        except Exception as e:
            step.details = _("Failed to check link status") + ": " + str(e)
            return False

    def _test_ip_configuration(self) -> bool:
        """Test IP address configuration."""
        step = self.steps[3]
        try:
            configured_interfaces = []

            interfaces = netifaces.interfaces()
            for iface in interfaces:
                if iface.startswith(("lo", "docker", "br-", "veth")):
                    continue

                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info.get("addr")
                        if ip and not ip.startswith(
                            "169.254"
                        ):  # Exclude APIPA addresses
                            configured_interfaces.append(f"{iface}({ip})")

            if configured_interfaces:
                step.details = (
                    _("Configured interfaces:") + " " + ", ".join(configured_interfaces)
                )
                return True
            else:
                step.details = _("No valid IP addresses configured")
                return False

        except Exception as e:
            step.details = _("Failed to check IP configuration") + ": " + str(e)
            return False

    def _test_default_route(self) -> bool:
        """Test default route configuration."""
        step = self.steps[4]
        try:
            gateways = netifaces.gateways()
            default_gw = gateways.get("default")

            if default_gw and netifaces.AF_INET in default_gw:
                gateway_ip = default_gw[netifaces.AF_INET][0]
                interface = default_gw[netifaces.AF_INET][1]
                step.details = (
                    _("Default gateway:")
                    + f" {gateway_ip} "
                    + _("via")
                    + f" {interface}"
                )
                return True
            else:
                step.details = _("No default gateway configured")
                return False

        except Exception as e:
            step.details = _("Failed to check default route") + ": " + str(e)
            return False

    def _test_gateway_connectivity(self) -> bool:
        """Test connectivity to default gateway."""
        step = self.steps[5]
        try:
            gateways = netifaces.gateways()
            default_gw = gateways.get("default")

            if not default_gw or netifaces.AF_INET not in default_gw:
                step.details = _("No default gateway to test")
                return False

            gateway_ip = default_gw[netifaces.AF_INET][0]

            # Ping the gateway
            result = subprocess.run(
                ["ping", "-c", "3", "-W", "2", gateway_ip],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Extract packet loss info
                lines = result.stdout.split("\n")
                for line in lines:
                    if "packet loss" in line:
                        step.details = (
                            _("Gateway")
                            + f" {gateway_ip} "
                            + _("reachable")
                            + " - "
                            + line.strip()
                        )
                        break
                else:
                    step.details = _("Gateway") + f" {gateway_ip} " + _("is reachable")
                return True
            else:
                step.details = _("Gateway") + f" {gateway_ip} " + _("is unreachable")
                return False

        except Exception as e:
            step.details = _("Failed to test gateway connectivity") + ": " + str(e)
            return False

    def _check_dns_configuration(self) -> bool:
        """Check and display configured DNS servers."""
        step = self.steps[6]
        try:
            # Get DNS servers from resolv.conf
            dns_servers = []
            try:
                with open("/etc/resolv.conf", "r") as f:
                    for line in f:
                        if line.startswith("nameserver"):
                            dns_servers.append(line.split()[1])
            except:
                pass

            if not dns_servers:
                # Try to get DNS from systemd-resolved
                try:
                    result = subprocess.run(
                        ["systemd-resolve", "--status"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    for line in result.stdout.split("\n"):
                        if "DNS Servers:" in line:
                            dns_part = line.split("DNS Servers:")[1].strip()
                            if dns_part:
                                dns_servers.extend(dns_part.split())
                except:
                    pass

            if not dns_servers:
                dns_servers = ["Using system default"]

            step.details = _("Configured DNS servers:") + " " + ", ".join(dns_servers)
            return True

        except Exception as e:
            step.details = _("Failed to check DNS configuration:") + " " + str(e)
            return False

    def _check_external_ip(self) -> bool:
        """Check and display external IPv4 and IPv6 addresses."""
        step = self.steps[8]
        try:
            # IPv4 services
            ipv4_services = [
                "https://api.ipify.org",
                "https://checkip.amazonaws.com",
                "https://ipinfo.io/ip",
            ]

            # IPv6 services
            ipv6_services = [
                "https://api6.ipify.org",
                "https://ipv6.icanhazip.com",
            ]

            external_ipv4 = None
            external_ipv6 = None

            # Check IPv4 and IPv6 in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                # Submit IPv4 tasks
                ipv4_futures = {
                    executor.submit(self._get_ip_from_service, service, 4): service
                    for service in ipv4_services
                }

                # Submit IPv6 tasks
                ipv6_futures = {
                    executor.submit(self._get_ip_from_service, service, 6): service
                    for service in ipv6_services
                }

                # Wait for IPv4 results
                for future in concurrent.futures.as_completed(ipv4_futures):
                    if external_ipv4:
                        break
                    try:
                        result = future.result()
                        if (
                            result
                            and result.strip()
                            and self._is_valid_ipv4(result.strip())
                        ):
                            external_ipv4 = result.strip()
                            break
                    except Exception:
                        continue

                # Wait for IPv6 results
                for future in concurrent.futures.as_completed(ipv6_futures):
                    if external_ipv6:
                        break
                    try:
                        result = future.result()
                        if (
                            result
                            and result.strip()
                            and self._is_valid_ipv6(result.strip())
                        ):
                            external_ipv6 = result.strip()
                            break
                    except Exception:
                        continue

            # Build result details
            results = []
            if external_ipv4:
                results.append(f"IPv4: {external_ipv4}")
            if external_ipv6:
                results.append(f"IPv6: {external_ipv6}")

            if results:
                step.details = _("External IP addresses:") + " " + ", ".join(results)
                return True
            else:
                step.details = _("Unable to determine external IP addresses")
                return False

        except Exception as e:
            step.details = _("Failed to check external IP:") + " " + str(e)
            return False

    def _is_valid_ipv4(self, ip: str) -> bool:
        """Check if string is a valid IPv4 address."""
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False

    def _is_valid_ipv6(self, ip: str) -> bool:
        """Check if string is a valid IPv6 address."""
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except socket.error:
            return False

    def _get_ip_from_service(self, service_url: str, ip_version: int = 4) -> str:
        """Get IP from a specific service for specified IP version."""
        try:
            # Configure requests session for IP version preference
            session = requests.Session()

            # For IPv6-specific services or when requesting IPv6
            if ip_version == 6:
                # Some services have IPv6-specific URLs
                if "api.ipify.org" in service_url:
                    service_url = service_url.replace("api.ipify.org", "api6.ipify.org")
                elif "icanhazip.com" in service_url and "ipv6" not in service_url:
                    service_url = "https://ipv6.icanhazip.com"

            response = session.get(service_url, timeout=5)
            if response.status_code == 200:
                ip_text = response.text.strip()
                # Validate that the returned IP matches the requested version
                if ip_version == 4 and self._is_valid_ipv4(ip_text):
                    return ip_text
                elif ip_version == 6 and self._is_valid_ipv6(ip_text):
                    return ip_text
                elif ip_version == 4 and not self._is_valid_ipv6(ip_text):
                    # For services that might return IPv4 without validation
                    return ip_text

        except Exception:
            pass
        return ""

    def _test_dns_resolution(self) -> bool:
        """Test DNS name resolution."""
        step = self.steps[7]
        try:
            test_domains = [
                "kernel.org",
                "gnu.org",
                "kde.org",
            ]
            resolved_domains = []

            # Test domain resolution in parallel
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(test_domains)
            ) as executor:
                future_to_domain = {
                    executor.submit(self._resolve_single_domain, domain): domain
                    for domain in test_domains
                }

                for future in concurrent.futures.as_completed(future_to_domain):
                    try:
                        result = future.result()
                        if result:
                            resolved_domains.append(result)
                    except Exception:
                        continue

            if resolved_domains:
                step.details = _("Resolved:") + " " + ", ".join(resolved_domains)
                return True
            else:
                step.details = (
                    _("Failed to resolve any test domains:")
                    + " "
                    + ", ".join(test_domains)
                )
                return False

        except Exception as e:
            step.details = _("Failed to test DNS resolution:") + " " + str(e)
            return False

    def _resolve_single_domain(self, domain: str) -> str:
        """Resolve a single domain name."""
        try:
            ip = socket.gethostbyname(domain)
            return f"{domain}({ip})"
        except Exception:
            return ""

    def _test_internet_access(self) -> bool:
        """Test internet access via HTTP."""
        step = self.steps[9]
        try:
            test_urls = [
                "http://cp.cloudflare.com/generate_204",
                "http://connectivitycheck.gstatic.com/generate_204",
            ]

            for url in test_urls:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code in [200, 204]:
                        step.details = _("Internet access confirmed via") + f" {url}"
                        return True
                except:
                    continue

            step.details = _("No internet access detected")
            return False

        except Exception as e:
            step.details = _("Failed to test internet access:") + " " + str(e)
            return False

    def _test_big_repositories(self) -> bool:
        """Test communication with big repositories"""
        step = self.steps[10]
        try:
            is_a_community_repository = False
            with open('/etc/pacman.conf', "r") as file:
                for line in file:
                    line = line.strip()

                    if line.startswith("#") or not line:
                        continue

                    if line.startswith("Server") and "communitybig" in line:
                        is_a_community_repository = True

            if is_a_community_repository:
                test_urls = [
                    "https://repo.communitybig.org",
                ]
            else:
                test_urls = [
                    "https://repo.biglinux.com.br",
                ]

            for url in test_urls:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code in [200, 204]:
                        step.details = _("Repository access confirmed") + f" {url}"
                        return True
                except:
                    continue

            step.details = _("Repository access not detected")
            return False

        except Exception as e:
            step.details = _("Failed to access repository:") + " " + str(e)
            return False

    def _notify_progress(self, step: DiagnosticStep) -> None:
        """Notify progress callback about step update."""
        if self.progress_callback:
            self.progress_callback(step)
