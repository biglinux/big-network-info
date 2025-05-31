"""
Configuration manager for custom services and application settings.
Handles loading, saving, and managing user-defined services and ports.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict

from .services import ServiceInfo, COMMON_SERVICES


@dataclass
class AppConfig:
    """Application configuration settings."""

    custom_services: List[Dict[str, Any]]
    scan_timeout: float  # Port scanning timeout
    scan_threads: int  # Number of parallel scanning threads
    use_privileged_scan: bool
    auto_detect_network: bool
    # New detection settings
    ping_timeout: float  # Ping timeout in seconds
    ping_attempts: int  # Number of ping attempts per host
    hostname_timeout: float  # Hostname resolution timeout
    discovery_threads: int  # Parallel threads for host discovery
    additional_settings: Dict[
        str, Any
    ]  # Additional settings like welcome screen preferences

    @classmethod
    def default(cls) -> "AppConfig":
        """Create default configuration."""
        return cls(
            custom_services=[],
            scan_timeout=1.0,
            scan_threads=130,
            use_privileged_scan=False,
            auto_detect_network=True,
            ping_timeout=1.0,
            ping_attempts=2,
            hostname_timeout=0.5,  # 500ms hostname resolution
            discovery_threads=130,  # 50 parallel discovery threads
            additional_settings={"show_welcome_on_startup": False},
        )


class ConfigManager:
    """Manages application configuration and custom services."""

    def __init__(self):
        """Initialize configuration manager."""
        self.config_dir = Path.home() / ".config" / "big-network-scanner"
        self.config_file = self.config_dir / "config.json"
        self.config = self.load_config()
        self._custom_services_cache = None
        # Additional settings dictionary for non-AppConfig settings
        self._additional_settings = {}
        self.load_additional_settings()

    def ensure_config_dir(self) -> None:
        """Ensure configuration directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> AppConfig:
        """
        Load configuration from file.

        Returns:
            Loaded configuration or default if file doesn't exist
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    print(f"DEBUG: Loading config from {self.config_file}")
                    print(f"DEBUG: Loaded data: {data}")
                    print(
                        f"DEBUG: Custom services in loaded data: {data.get('custom_services', [])}"
                    )
                    config = AppConfig(**data)
                    print(f"DEBUG: AppConfig custom_services: {config.custom_services}")
                    return config
            else:
                print(
                    f"DEBUG: Config file {self.config_file} doesn't exist, using default"
                )
                return AppConfig.default()
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            # If config is corrupted, return default
            print(f"DEBUG: Error loading config: {e}, using default")
            return AppConfig.default()

    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            self.ensure_config_dir()
            config_data = asdict(self.config)
            config_data["additional_settings"] = self._additional_settings
            print(f"DEBUG: Saving config data: {config_data}")
            print(
                f"DEBUG: Custom services in data: {config_data.get('custom_services', [])}"
            )
            with open(self.config_file, "w") as f:
                json.dump(config_data, f, indent=2)
            print(f"DEBUG: Successfully saved config to {self.config_file}")
        except Exception as e:
            print(f"Failed to save configuration: {e}")

    def load_additional_settings(self) -> None:
        """Load additional settings from config file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    self._additional_settings = data.get("additional_settings", {})
        except (json.JSONDecodeError, KeyError):
            self._additional_settings = {}

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get an additional setting value.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        return self._additional_settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """
        Set an additional setting value.

        Args:
            key: Setting key
            value: Setting value
        """
        self._additional_settings[key] = value

    def get_all_services(self) -> List[ServiceInfo]:
        """
        Get all services including built-in and custom ones.

        Returns:
            Combined list of all services
        """
        all_services = list(COMMON_SERVICES)

        # Add custom services
        for custom_data in self.config.custom_services:
            try:
                service = ServiceInfo(
                    name=custom_data["name"],
                    port=custom_data["port"],
                    protocol=custom_data["protocol"],
                    description=custom_data["description"],
                    access_method=custom_data.get("access_method", ""),
                )
                all_services.append(service)
            except KeyError:
                # Skip malformed custom services
                continue

        return all_services

    def get_custom_services(self) -> List[ServiceInfo]:
        """
        Get only custom services.

        Returns:
            List of custom services
        """
        custom_services = []
        for custom_data in self.config.custom_services:
            try:
                service = ServiceInfo(
                    name=custom_data["name"],
                    port=custom_data["port"],
                    protocol=custom_data["protocol"],
                    description=custom_data["description"],
                    access_method=custom_data.get("access_method", ""),
                )
                custom_services.append(service)
            except KeyError:
                continue
        return custom_services

    def add_custom_service(self, service: ServiceInfo) -> bool:
        """
        Add a custom service.

        Args:
            service: Service information to add

        Returns:
            True if added successfully, False if already exists
        """
        # Check if service already exists (same port and protocol)
        for existing in self.config.custom_services:
            if (
                existing["port"] == service.port
                and existing["protocol"] == service.protocol
            ):
                return False

        # Add new service
        service_dict = {
            "name": service.name,
            "port": service.port,
            "protocol": service.protocol,
            "description": service.description,
            "access_method": service.access_method,
        }

        print(f"DEBUG: Adding custom service: {service_dict}")
        self.config.custom_services.append(service_dict)
        print(
            f"DEBUG: Total custom services after add: {len(self.config.custom_services)}"
        )
        print(f"DEBUG: Custom services list: {self.config.custom_services}")
        self.save_config()
        print(f"DEBUG: Config saved to {self.config_file}")
        return True

    def remove_custom_service(self, port: int, protocol: str) -> bool:
        """
        Remove a custom service by port and protocol.

        Args:
            port: Port number
            protocol: Protocol (tcp/udp)

        Returns:
            True if removed, False if not found
        """
        for i, service in enumerate(self.config.custom_services):
            if service["port"] == port and service["protocol"] == protocol:
                del self.config.custom_services[i]
                self.save_config()
                return True
        return False

    def update_custom_service(
        self, old_port: int, old_protocol: str, new_service: ServiceInfo
    ) -> bool:
        """
        Update an existing custom service.

        Args:
            old_port: Original port number
            old_protocol: Original protocol
            new_service: New service information

        Returns:
            True if updated successfully
        """
        for i, service in enumerate(self.config.custom_services):
            if service["port"] == old_port and service["protocol"] == old_protocol:
                self.config.custom_services[i] = {
                    "name": new_service.name,
                    "port": new_service.port,
                    "protocol": new_service.protocol,
                    "description": new_service.description,
                    "access_method": new_service.access_method,
                }
                self.save_config()
                return True
        return False

    def is_port_in_use(
        self, port: int, protocol: str, exclude_service: ServiceInfo = None
    ) -> bool:
        """
        Check if a port/protocol combination is already in use.

        Args:
            port: Port number
            protocol: Protocol
            exclude_service: Service to exclude from check (for updates)

        Returns:
            True if port is already in use
        """
        # Check built-in services
        for service in COMMON_SERVICES:
            if (
                service.port == port
                and service.protocol == protocol
                and service != exclude_service
            ):
                return True

        # Check custom services
        for service_data in self.config.custom_services:
            if service_data["port"] == port and service_data["protocol"] == protocol:
                if exclude_service is None:
                    return True
                elif (
                    service_data["port"] != exclude_service.port
                    or service_data["protocol"] != exclude_service.protocol
                ):
                    return True

        return False

    def reset_custom_services(self) -> None:
        """Reset all custom services to empty list."""
        self.config.custom_services = []
        self.save_config()

    def export_custom_services(self, file_path: str) -> bool:
        """
        Export custom services to a JSON file.

        Args:
            file_path: Path to export file

        Returns:
            True if exported successfully
        """
        try:
            export_data = {
                "version": "1.0",
                "exported_at": str(Path(__file__).stat().st_mtime),
                "custom_services": self.config.custom_services,
            }

            with open(file_path, "w") as f:
                json.dump(export_data, f, indent=2)
            return True
        except Exception:
            return False

    def import_custom_services(
        self, file_path: str, replace: bool = False
    ) -> tuple[bool, int]:
        """
        Import custom services from a JSON file.

        Args:
            file_path: Path to import file
            replace: If True, replace all existing custom services

        Returns:
            Tuple of (success, number_imported)
        """
        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            if replace:
                self.config.custom_services = []

            imported_count = 0
            for service_data in data.get("custom_services", []):
                try:
                    service = ServiceInfo(
                        name=service_data["name"],
                        port=service_data["port"],
                        protocol=service_data["protocol"],
                        description=service_data["description"],
                        access_method=service_data.get("access_method", ""),
                    )

                    if not self.is_port_in_use(service.port, service.protocol):
                        if self.add_custom_service(service):
                            imported_count += 1
                except KeyError:
                    continue

            return True, imported_count
        except Exception:
            return False, 0
