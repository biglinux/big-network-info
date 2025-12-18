#!/usr/bin/env python3
"""
WiFi Scanner module for network analysis and visualization
"""

import subprocess
import re
import threading
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

# Enable debug logging for WiFi scanner
logging.basicConfig(level=logging.DEBUG)


@dataclass
class WiFiNetwork:
    """Represents a WiFi network with its properties"""

    ssid: str
    bssid: str
    channel: int
    frequency: float
    signal_level: int  # 0-100 percentage scale from nmcli
    encryption: str
    quality: int
    timestamp: datetime

    def __post_init__(self):
        """Ensure quality matches signal level for 0-100 scale"""
        if self.quality == 0 and self.signal_level:
            self.quality = self.signal_level


class WiFiScanner:
    """WiFi scanner that collects network information for analysis"""

    def __init__(self):
        self.networks_history: Dict[str, List[WiFiNetwork]] = {}
        self.scanning = False
        self.scan_thread: Optional[threading.Thread] = None
        self.scan_interval = 1.0  # Default 1 second
        self.max_history_minutes = 10  # Keep 10 minutes of history
        self.callbacks = []
        self.lock = threading.Lock()

    def add_callback(self, callback):
        """Add a callback function to be called when new data is available"""
        self.callbacks.append(callback)

    def set_scan_interval(self, interval: float):
        """Set the scanning interval in seconds"""
        self.scan_interval = max(1.0, interval)  # Minimum 1 second

    def _notify_callbacks(self):
        """Notify all registered callbacks about new data"""
        for callback in self.callbacks:
            try:
                callback(self.get_current_networks(), self.get_channel_usage())
            except Exception as e:
                logging.error(f"Error in WiFi scanner callback: {e}")

    def _scan_with_nmcli(self) -> List[WiFiNetwork]:
        """Scan WiFi networks using nmcli"""
        networks = []
        try:
            # Rescan with --rescan yes and get results
            subprocess.run(
                ["nmcli", "device", "wifi", "rescan", "--rescan", "yes"],
                capture_output=True,
                timeout=10,
            )
            time.sleep(1)

            result = subprocess.run(
                [
                    "nmcli",
                    "-t",
                    "-f",
                    "SSID,BSSID,MODE,CHAN,FREQ,RATE,SIGNAL,BARS,SECURITY",
                    "device",
                    "wifi",
                    "list",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return networks

            lines = result.stdout.strip().split("\n")
            for line in lines:
                if not line:
                    continue

                # Split by unescaped colons only
                parts = []
                current_part = ""
                i = 0
                while i < len(line):
                    if line[i] == "\\" and i + 1 < len(line) and line[i + 1] == ":":
                        current_part += ":"
                        i += 2
                    elif line[i] == ":":
                        parts.append(current_part)
                        current_part = ""
                        i += 1
                    else:
                        current_part += line[i]
                        i += 1
                if current_part:
                    parts.append(current_part)

                if len(parts) >= 9:
                    ssid = parts[0] if parts[0] else "Hidden Network"
                    bssid = parts[1]  # BSSID is already properly formatted
                    channel = int(parts[3]) if parts[3].isdigit() else 0
                    logging.debug(
                        f"Parsed channel for {ssid}: {channel} (from '{parts[3]}')"
                    )

                    # Parse frequency - can be "2447 MHz" format
                    freq_str = parts[4].strip()
                    if "MHz" in freq_str:
                        freq_match = re.search(r"(\d+)", freq_str)
                        frequency = (
                            float(freq_match.group(1)) / 1000 if freq_match else 0.0
                        )  # MHz to GHz
                    elif freq_str.isdigit():
                        frequency = float(freq_str) / 1000  # MHz to GHz
                    else:
                        frequency = 0.0

                    # Parse signal strength - nmcli returns percentage (0-100)
                    # Keep the original 0-100 scale instead of converting to dBm
                    signal_str = parts[6].strip()
                    logging.debug(f"Parsing signal for {ssid}: '{signal_str}'")

                    if signal_str.isdigit():
                        signal_percent = int(signal_str)
                        # Use the original percentage as signal level (0-100 scale)
                        signal = signal_percent
                        quality = signal_percent  # Same as signal for nmcli
                        logging.debug(
                            f"Using original signal strength {signal_percent}% for {ssid}"
                        )
                    elif signal_str.lstrip("-").isdigit():
                        # If somehow in dBm format, convert to percentage
                        dBm_val = int(signal_str)
                        if dBm_val <= -20:
                            # Convert dBm to percentage approximation
                            if dBm_val >= -30:
                                signal = 100
                            elif dBm_val >= -50:
                                signal = 80 + int((dBm_val + 50) * 20 / 20)  # 80-100%
                            elif dBm_val >= -70:
                                signal = 50 + int((dBm_val + 70) * 30 / 20)  # 50-80%
                            elif dBm_val >= -90:
                                signal = 20 + int((dBm_val + 90) * 30 / 20)  # 20-50%
                            else:
                                signal = max(
                                    0, 20 + int((dBm_val + 100) * 20 / 10)
                                )  # 0-20%
                        else:
                            signal = max(0, min(100, dBm_val))  # Clamp to 0-100
                        quality = signal
                    else:
                        # Try to extract numbers from the string
                        signal_match = re.search(r"-?\d+", signal_str)
                        if signal_match:
                            val = int(signal_match.group())
                            if val > 0 and val <= 100:
                                # Looks like percentage, use as-is
                                signal = val
                                quality = val
                            elif val < 0:
                                # Looks like dBm, convert to percentage
                                if val >= -30:
                                    signal = 100
                                elif val >= -50:
                                    signal = 80 + int((val + 50) * 20 / 20)
                                elif val >= -70:
                                    signal = 50 + int((val + 70) * 30 / 20)
                                elif val >= -90:
                                    signal = 20 + int((val + 90) * 30 / 20)
                                else:
                                    signal = max(0, 20 + int((val + 100) * 20 / 10))
                                quality = signal
                            else:
                                signal = min(100, val)  # Clamp to 100 max
                                quality = signal
                        else:
                            signal = 0
                            quality = 0
                        logging.debug(
                            f"Extracted signal: {signal}% from '{signal_str}'"
                        )

                    security = parts[8] if parts[8] else "Open"

                    logging.debug(
                        f"Network: {ssid}, Signal: {signal}% (from {signal_str})"
                    )

                    network = WiFiNetwork(
                        ssid=ssid,
                        bssid=bssid,
                        channel=channel,
                        frequency=frequency,
                        signal_level=signal,
                        encryption=security,
                        quality=quality,
                        timestamp=datetime.now(),
                    )
                    networks.append(network)

        except subprocess.TimeoutExpired:
            logging.error("WiFi scan timeout with nmcli")
        except Exception as e:
            logging.error(f"Error scanning with nmcli: {e}")

        return networks

    def scan_networks(self) -> List[WiFiNetwork]:
        """Scan for WiFi networks using available tools"""
        networks = []

        # Try nmcli first (more reliable and doesn't require sudo)
        try:
            networks = self._scan_with_nmcli()
            if networks:
                logging.info(f"Found {len(networks)} networks with nmcli")
                return networks
        except Exception as e:
            logging.warning(f"nmcli scan failed: {e}")

        return networks

    def _cleanup_old_data(self):
        """Remove data older than max_history_minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=self.max_history_minutes)

        with self.lock:
            for ssid in list(self.networks_history.keys()):
                # Filter out old entries
                self.networks_history[ssid] = [
                    network
                    for network in self.networks_history[ssid]
                    if network.timestamp > cutoff_time
                ]

                # Remove empty entries
                if not self.networks_history[ssid]:
                    del self.networks_history[ssid]

    def _scan_loop(self):
        """Main scanning loop"""
        while self.scanning:
            try:
                networks = self.scan_networks()
                current_time = datetime.now()

                with self.lock:
                    # Keep track of currently detected network keys
                    current_network_keys = set()

                    # Add new data to history - use BSSID+SSID as unique key to handle multiple APs
                    for network in networks:
                        # Create unique key for each access point
                        if network.ssid == "Hidden Network" or not network.ssid:
                            # For hidden networks, use BSSID as identifier
                            network_key = f"Hidden-{network.bssid}"
                        else:
                            # For named networks, use SSID+BSSID to distinguish multiple APs
                            network_key = f"{network.ssid}@{network.bssid}"

                        current_network_keys.add(network_key)

                        if network_key not in self.networks_history:
                            self.networks_history[network_key] = []
                        self.networks_history[network_key].append(network)

                    # Handle missing networks - add zero signal data points for networks that disappeared
                    # Only check networks that have been seen in the last few minutes to avoid old data
                    recent_cutoff = current_time - timedelta(minutes=2)

                    for network_key, history in list(self.networks_history.items()):
                        if not history:
                            continue

                        # Check if this network was recently active but is now missing
                        last_network = history[-1]
                        if (
                            network_key not in current_network_keys
                            and last_network.timestamp > recent_cutoff
                            and last_network.signal_level > 0
                        ):  # Only if last signal was not already 0
                            # Create a zero signal data point for the missing network
                            zero_signal_network = WiFiNetwork(
                                ssid=last_network.ssid,
                                bssid=last_network.bssid,
                                channel=last_network.channel,
                                frequency=last_network.frequency,
                                signal_level=0,  # Set signal to 0 for missing network
                                encryption=last_network.encryption,
                                quality=0,
                                timestamp=current_time,
                            )

                            # Add the zero signal point to history
                            self.networks_history[network_key].append(
                                zero_signal_network
                            )
                            logging.debug(
                                f"Added zero signal point for missing network: {network_key}"
                            )

                # Cleanup old data
                self._cleanup_old_data()

                # Notify callbacks
                self._notify_callbacks()

            except Exception as e:
                logging.error(f"Error in WiFi scan loop: {e}")

            # Wait for next scan
            for _ in range(int(self.scan_interval * 10)):
                if not self.scanning:
                    break
                time.sleep(0.1)

    def start_scanning(self):
        """Start continuous WiFi scanning"""
        if self.scanning:
            return

        self.scanning = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        logging.info("WiFi scanning started")

    def stop_scanning(self):
        """Stop WiFi scanning"""
        self.scanning = False
        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join(timeout=2)
        logging.info("WiFi scanning stopped")

    def get_current_networks(self) -> Dict[str, WiFiNetwork]:
        """Get the most recent data for each network"""
        current_networks = {}

        with self.lock:
            for ssid, history in self.networks_history.items():
                if history:
                    # Get the most recent entry
                    current_networks[ssid] = history[-1]

        return current_networks

    def get_all_history(self, minutes: int = 2) -> Dict[str, List[WiFiNetwork]]:
        """Get history for all networks for the last N minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        history = {}

        with self.lock:
            for ssid, networks in self.networks_history.items():
                recent_networks = [
                    network for network in networks if network.timestamp > cutoff_time
                ]
                if recent_networks:
                    history[ssid] = recent_networks

        return history

    def get_channel_usage(self) -> Dict[int, List[str]]:
        """Get current channel usage by all networks"""
        current_networks = self.get_current_networks()
        channel_usage = {}

        for network_key, network in current_networks.items():
            # Skip networks with invalid channel data
            if network.channel <= 0 or network.channel > 200:
                continue

            if network.channel not in channel_usage:
                channel_usage[network.channel] = []

            # Use display name for the network
            display_name = (
                network.ssid
                if network.ssid and network.ssid != "Hidden Network"
                else f"Hidden-{network.bssid[-8:]}"
            )
            channel_usage[network.channel].append(display_name)

        return channel_usage
