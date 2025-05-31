# Big Network Info

![License](https://img.shields.io/badge/license-GPL%20v2-blue.svg) ![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg) ![GTK4](https://img.shields.io/badge/gtk4-supported-green.svg)

Big Network Info is a modern GTK4 application to discover network devices, analyze WiFi networks, detect open services, and troubleshoot connectivity issues with ease.

![image](https://github.com/user-attachments/assets/e9dda6ce-f1d8-4110-b4a1-6658e9221118)

![image](https://github.com/user-attachments/assets/f162907d-fdb5-4fce-ade2-1177dd9a8ac7)

![image](https://github.com/user-attachments/assets/9c607322-b8f9-49fe-be76-2a26349999a3)

![image](https://github.com/user-attachments/assets/f8ea0f40-c705-462d-a5be-104d99d0f738)

![image](https://github.com/user-attachments/assets/03fe3149-e6f9-4222-9dbc-64860d31dba4)

![image](https://github.com/user-attachments/assets/adb82edd-2e9c-4431-bba5-9261b0626487)

![image](https://github.com/user-attachments/assets/abd912f2-cd8e-4bc1-ae60-3a7a3d3378c0)

![image](https://github.com/user-attachments/assets/526d53f0-05a8-4fd7-b6c5-9434bc26b915)


## Key Features

- **Network Diagnostics:**
  - Test network interface status and link connectivity.
  - Verify IP configuration, default gateway, and DNS settings.
  - Test DNS resolution and internet access.
  - Determine external IP address (IPv4 & IPv6).
  - Parallel execution of diagnostic steps for speed.
- **Device Discovery (Network Scan):**
  - Discover live hosts on the specified network range.
  - Enhanced host discovery using Ping, ARP table, and TCP probes.
  - Resolve hostnames using standard DNS and Avahi (mDNS for local devices).
  - Identify MAC addresses and vendor information (requires `ieee-oui.txt`).
- **Service Detection:**
  - Scan for common network services (HTTP, HTTPS, SSH, FTP, SMB, RDP, etc.).
  - Support for custom user-defined services and ports.
  - Parallel port scanning for faster results.
- **Modern GTK4 Interface:**
  - User-friendly GUI built with LibAdwaita for a clean, modern look.
  - Tabbed interface for Diagnostics, Device Scanning, and Settings.
  - Real-time progress updates for scans and diagnostics.
  - Interactive results display with options to open services, copy information, and ping devices.
  - Built-in ping utility.
- **Configuration Management:**
  - Adjust scan parameters: timeouts (ping, hostname, port scan), thread counts (discovery, port scan).
  - Manage custom services: add, edit, remove, import/export from JSON.
  - Persistent configuration stored in `~/.config/big-network-scanner/config.json`.
- **Reporting:**
  - Export detailed network scan results to PDF.
  - Export network diagnostics reports to PDF.
- **Internationalization:**
  - Supports translations (uses `gettext`).
- **Welcome Screen:**
  - Provides an overview of features on first launch or when manually shown.
  - Option to disable welcome screen on startup.

## 📋 Requirements

### Software
*   Python 3.10+
*   GTK4
*   LibAdwaita

### Python Libraries
These will be installed via `pip`. A `requirements.txt` should be created.
*   `netifaces`
*   `requests`
*   `reportlab`
*   `PyGObject` (usually installed with GTK bindings)

### System Tools & Files
These tools are generally expected to be available on a Linux system. The application uses them via `subprocess`.
*   `ping`
*   `ip` (from `iproute2` package: `ip link`, `ip addr`, `ip route`, `ip neigh`)
*   `arp` (from `net-tools` package, used as a fallback if `ip neigh` fails or isn't preferred)
*   `avahi-resolve` & `avahi-browse` (from `avahi` package, for enhanced local hostname resolution and service discovery)
*   `xdg-open` (for opening URLs, SFTP, SMB links in default applications)
*   A terminal emulator (e.g., `gnome-terminal`, `konsole`, `xfce4-terminal`, `xterm`) for SSH connections.
*   **(Highly Recommended for Vendor Info)** `ieee-oui.txt`: Typically located at `/usr/share/arp-scan/ieee-oui.txt` or similar paths. This file is used for MAC address to vendor mapping. On Arch Linux, this is provided by the `arp-scan` package.

## 🚀 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/biglinux/big-network-info.git
    cd big-network-info
    ```

2.  **Set up a Python virtual environment (recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install system dependencies:**

    *   **For Arch Linux / BigLinux:**
        ```bash
        sudo pacman -Syu gtk4 libadwaita python-gobject \
                        python-netifaces python-requests python-reportlab \
                        iproute2 net-tools avahi arp-scan xdg-utils
        ```
        *(Note: `arp-scan` provides `ieee-oui.txt` and `arp-scan` utility, `net-tools` provides `arp`)*

    *   **For Debian/Ubuntu based systems:**
        ```bash
        sudo apt update
        sudo apt install gir1.2-gtk-4.0 gir1.2-adw-1 \
                         python3-gi python3-gi-cairo \
                         python3-netifaces python3-requests python3-reportlab \
                         iproute2 net-tools avahi-daemon avahi-utils arp-scan xdg-utils
        ```

    *   **For Fedora:**
        ```bash
        sudo dnf install gtk4 libadwaita python3-gobject \
                         python3-netifaces python3-requests python3-reportlab \
                         iproute net-tools avahi avahi-tools arp-scan xdg-utils
        ```
    *Ensure you have a terminal emulator installed if you want to use the SSH "Open in Terminal" feature (e.g., `gnome-terminal`, `konsole`).*

4.  **Install Python dependencies:**
    Create a `requirements.txt` file in the project root:
    ```txt
    # requirements.txt
    netifaces
    requests
    reportlab
    # PyGObject is usually handled by system package manager, but can be listed if needed
    # PyGObject
    ```
    Then install them:
    ```bash
    pip install -r requirements.txt
    ```

    
## 🏃 Running the Application

Once all dependencies are installed, you can run the application from the project's root directory:

```bash
python main.py
```


## ⚙️ Configuration

*   Application settings, including custom services and scan parameters, are stored in:
    `~/.config/big-network-scanner/config.json`
*   These settings can be managed through the "Settings" tab within the application.
*   The "Show welcome on startup" preference is also stored here.


## 🤝 Contributing

Contributions are welcome! If you'd like to contribute, please:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes.
4.  Ensure your code follows the existing style.
5.  Test your changes thoroughly.
6.  Submit a pull request with a clear description of your changes.

## 📜 License

This project is licensed under the **GNU General Public License v2.0**. See the [LICENSE](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html) file or link for details.
