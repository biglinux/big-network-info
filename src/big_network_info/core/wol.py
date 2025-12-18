"""
Wake-on-LAN (WoL) utility module.
Sends magic packets to wake up network devices remotely.
"""

import socket
import struct
import re
from typing import Optional


class WakeOnLan:
    """Wake-on-LAN packet sender for waking network devices."""
    
    # Default WoL port
    WOL_PORT = 9
    
    # Broadcast address
    BROADCAST_ADDR = "255.255.255.255"
    
    @staticmethod
    def validate_mac(mac_address: str) -> bool:
        """
        Validate MAC address format.
        
        Args:
            mac_address: MAC address string
            
        Returns:
            True if valid, False otherwise
        """
        # Accept formats: AA:BB:CC:DD:EE:FF, AA-BB-CC-DD-EE-FF, AABBCCDDEEFF
        pattern = r"^([0-9A-Fa-f]{2}[:-]?){5}([0-9A-Fa-f]{2})$"
        return bool(re.match(pattern, mac_address.replace(" ", "")))
    
    @staticmethod
    def normalize_mac(mac_address: str) -> str:
        """
        Normalize MAC address to standard format (lowercase, colon-separated).
        
        Args:
            mac_address: MAC address in any format
            
        Returns:
            Normalized MAC address (e.g., "aa:bb:cc:dd:ee:ff")
        """
        # Remove separators and spaces
        clean_mac = mac_address.replace(":", "").replace("-", "").replace(" ", "").lower()
        # Insert colons
        return ":".join(clean_mac[i:i+2] for i in range(0, 12, 2))
    
    @staticmethod
    def create_magic_packet(mac_address: str) -> bytes:
        """
        Create a Wake-on-LAN magic packet.
        
        The magic packet consists of:
        - 6 bytes of 0xFF (synchronization stream)
        - 16 repetitions of the target MAC address (96 bytes)
        - Total: 102 bytes
        
        Args:
            mac_address: Target device MAC address
            
        Returns:
            Magic packet bytes
            
        Raises:
            ValueError: If MAC address is invalid
        """
        if not WakeOnLan.validate_mac(mac_address):
            raise ValueError(f"Invalid MAC address: {mac_address}")
        
        # Normalize and convert MAC to bytes
        clean_mac = mac_address.replace(":", "").replace("-", "").replace(" ", "")
        mac_bytes = bytes.fromhex(clean_mac)
        
        # Create magic packet: 6 bytes of 0xFF + 16 repetitions of MAC
        sync_stream = b"\xff" * 6
        magic_packet = sync_stream + mac_bytes * 16
        
        return magic_packet
    
    @staticmethod
    def send_magic_packet(
        mac_address: str,
        ip_address: Optional[str] = None,
        port: int = WOL_PORT,
        interface: Optional[str] = None
    ) -> bool:
        """
        Send a Wake-on-LAN magic packet to wake a device.
        
        Args:
            mac_address: Target device MAC address
            ip_address: Broadcast IP address (default: 255.255.255.255)
            port: UDP port (default: 9)
            interface: Network interface IP to bind to (optional)
            
        Returns:
            True if packet was sent successfully, False otherwise
        """
        try:
            magic_packet = WakeOnLan.create_magic_packet(mac_address)
            broadcast_ip = ip_address or WakeOnLan.BROADCAST_ADDR
            
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Bind to specific interface if provided
            if interface:
                sock.bind((interface, 0))
            
            # Send the magic packet
            sock.sendto(magic_packet, (broadcast_ip, port))
            sock.close()
            
            return True
            
        except Exception as e:
            print(f"Failed to send WoL packet: {e}")
            return False
    
    @staticmethod
    def send_to_subnet(
        mac_address: str,
        subnet: str,
        port: int = WOL_PORT
    ) -> bool:
        """
        Send WoL packet to a specific subnet broadcast address.
        
        Args:
            mac_address: Target device MAC address
            subnet: Subnet in CIDR notation (e.g., "192.168.1.0/24")
            port: UDP port (default: 9)
            
        Returns:
            True if successful, False otherwise
        """
        import ipaddress
        try:
            network = ipaddress.ip_network(subnet, strict=False)
            broadcast_ip = str(network.broadcast_address)
            return WakeOnLan.send_magic_packet(mac_address, broadcast_ip, port)
        except ValueError:
            return False


def wake_device(mac_address: str, broadcast_ip: Optional[str] = None) -> bool:
    """
    Convenience function to wake a device by MAC address.
    
    Args:
        mac_address: Target device MAC address
        broadcast_ip: Optional broadcast IP for the network
        
    Returns:
        True if packet was sent, False otherwise
    """
    return WakeOnLan.send_magic_packet(mac_address, broadcast_ip)
