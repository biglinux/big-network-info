"""
Main application window for the network scanner.
Modern GTK4 interface with Adwaita styling.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib, Gio, Gdk
from .translation import _
import threading
import webbrowser
import subprocess
from typing import List, Optional

from ..core.scanner import NetworkScanner, ScanResult
from ..core.services import ServiceInfo
from ..core.config import ConfigManager
from ..core.network_diagnostics import (
    NetworkDiagnostics,
    DiagnosticStep,
    DiagnosticStatus,
)
from .components import ScanResultsView, LoadingView
from .welcome_screen import WelcomeScreen
from .wifi_analyzer import WiFiAnalyzerView
from ..utils.pdf_exporter import PDFExporter


class NetworkScannerApp(Adw.Application):
    """Main application class for the network scanner."""

    def __init__(self):
        """Initialize the application."""
        super().__init__(application_id="br.com.biglinux.networkinfo")
        self.window: Optional[Adw.ApplicationWindow] = None
        self.scanner: Optional[NetworkScanner] = None
        self.config_manager = ConfigManager()
        self.current_results: List[ScanResult] = []
        self.scanning_thread: Optional[threading.Thread] = None

    def do_activate(self):
        """Activate the application and create the main window."""
        if not self.window:
            self.window = self.create_main_window()
        self.window.present()

        # Show welcome screen if configured to do so
        if WelcomeScreen.should_show_on_startup(self.config_manager):
            # Wait for window to be properly mapped before showing welcome
            self.window.connect("notify::is-active", self._on_window_ready_for_welcome)

    def _on_window_ready_for_welcome(self, window, *args) -> None:
        """Show welcome screen once the main window is ready."""
        if window.get_mapped():
            # Disconnect this handler to avoid multiple calls
            window.disconnect_by_func(self._on_window_ready_for_welcome)
            # Small delay to ensure window positioning is complete
            GLib.idle_add(
                lambda: WelcomeScreen.show_welcome(self.window, self.config_manager)
            )

    def create_main_window(self) -> Adw.ApplicationWindow:
        """
        Create and setup the main application window.

        Returns:
            The configured main window
        """
        # Create main window
        window = Adw.ApplicationWindow(application=self)
        window.set_title(_("Big Network Info - Network Scanner"))
        window.set_default_size(940, 640)

        # Set window icon for taskbar (important for Wayland)
        window.set_icon_name("big-network-info")

        # Connect cleanup handler
        window.connect("destroy", self._on_window_destroy)

        # Create main content area with header bar
        # Create main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Create header bar with integrated tabs
        header_bar = Adw.HeaderBar()
        header_bar.set_hexpand(True)

        # Create proper window title with app icon using Adwaita style
        window_title = Adw.WindowTitle()

        # Create icon for the title
        icon_image = Gtk.Image()
        icon_image.set_from_icon_name("big-network-info")
        icon_image.set_pixel_size(24)

        # Create a box to hold icon and title together
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.set_halign(Gtk.Align.CENTER)
        title_box.append(icon_image)
        title_box.append(window_title)

        # Create tab buttons container
        self.tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.tab_box.add_css_class("linked")
        self.tab_box.set_halign(Gtk.Align.CENTER)

        # Create tab buttons
        self.diagnostics_button = Gtk.Button(label=_("Diagnostics"))
        self.diagnostics_button.connect("clicked", self._on_tab_clicked, "diagnostics")
        self.diagnostics_button.add_css_class("suggested-action")
        self.tab_box.append(self.diagnostics_button)

        self.devices_button = Gtk.Button(label=_("Find Devices"))
        self.devices_button.connect("clicked", self._on_tab_clicked, "devices")
        self.tab_box.append(self.devices_button)

        self.wifi_analyzer_button = Gtk.Button(label=_("WiFi Analyzer"))
        self.wifi_analyzer_button.connect(
            "clicked", self._on_tab_clicked, "wifi_analyzer"
        )
        self.tab_box.append(self.wifi_analyzer_button)

        self.settings_button = Gtk.Button(label=_("Settings"))
        self.settings_button.connect("clicked", self._on_tab_clicked, "settings")
        self.tab_box.append(self.settings_button)

        # Store buttons for easy access
        self.tab_buttons = {
            "diagnostics": self.diagnostics_button,
            "devices": self.devices_button,
            "wifi_analyzer": self.wifi_analyzer_button,
            "settings": self.settings_button,
        }

        # Set title widget for header bar
        header_bar.set_title_widget(self.tab_box)

        # Add the title box to the start of the header
        header_bar.pack_start(title_box)

        # Create menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text(_("Menu"))

        # Create menu
        menu_model = Gio.Menu()
        menu_model.append(_("Show Welcome Screen"), "app.welcome")
        menu_model.append(_("About"), "app.about")
        menu_model.append(_("Quit"), "app.quit")
        menu_button.set_menu_model(menu_model)

        header_bar.pack_end(menu_button)

        # Set window content
        window.set_content(main_box)
        main_box.append(header_bar)

        # Create stack for content switching
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.content_stack.set_transition_duration(300)
        main_box.append(self.content_stack)

        # Create and add tab content
        self.diagnostics_view = self.create_diagnostics_tab_view()
        self.content_stack.add_named(self.diagnostics_view, "diagnostics")

        self.scanner_view = self.create_scanner_tab_view()
        self.content_stack.add_named(self.scanner_view, "devices")

        self.wifi_analyzer_view = WiFiAnalyzerView()
        self.content_stack.add_named(self.wifi_analyzer_view, "wifi_analyzer")

        self.settings_view = self.create_combined_settings_view()
        self.content_stack.add_named(self.settings_view, "settings")

        # Start with diagnostics tab
        self.current_tab = "diagnostics"
        self.content_stack.set_visible_child_name("diagnostics")

        # Create application actions
        self.create_actions()

        # No need to explicitly set initial tab: defaults to first (Home)

        return window

    def create_actions(self) -> None:
        """Create application actions."""
        # Welcome action
        welcome_action = Gio.SimpleAction.new("welcome", None)
        welcome_action.connect("activate", self.on_welcome)
        self.add_action(welcome_action)

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about)
        self.add_action(about_action)

        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit)
        self.add_action(quit_action)

        # Keyboard shortcuts
        self.set_accels_for_action("app.quit", ["<Ctrl>q"])

    def on_auto_detect(self, button: Gtk.Button) -> None:
        """Handle auto-detect network range button click."""
        if not self.scanner:
            self.scanner = NetworkScanner(config_manager=self.config_manager)

        network_range = self.scanner.get_local_network_range()
        self.range_row.set_text(network_range)

    def on_start_diagnostics(self, button: Gtk.Button) -> None:
        """Handle start diagnostics button click."""
        # Switch to diagnostics running view
        self.diagnostics_stack.set_visible_child_name("running")
        self.run_network_diagnostics()

    def on_back_to_diagnostics_welcome(self, button: Gtk.Button) -> None:
        """Handle back to diagnostics welcome button click."""
        self.diagnostics_stack.set_visible_child_name("welcome")

    def start_scan(self, network_range: str) -> None:
        """
        Start network scanning in background thread.

        Args:
            network_range: Network range to scan
        """
        # Store the current network range for later use (e.g., PDF export)
        self.current_network_range = network_range

        # Switch to Find Devices tab
        self.activate_tab("devices")

        # Reset any previous scanner state
        if self.scanner:
            self.scanner.stop_scan()

        # Wait for any existing thread to finish
        if self.scanning_thread and self.scanning_thread.is_alive():
            self.scanning_thread.join(timeout=2.0)

        # Switch to scanning view
        self.scanner_stack.set_visible_child_name("scanning")

        # Create scanner with progress callback (auto-detect privilege mode)
        self.scanner = NetworkScanner(
            progress_callback=self.on_scan_progress, config_manager=self.config_manager
        )

        # Start scanning thread
        self.scanning_thread = threading.Thread(
            target=self.scan_worker, args=(network_range,), daemon=True
        )
        self.scanning_thread.start()

    def scan_worker(self, network_range: str) -> None:
        """
        Worker function for network scanning.

        Args:
            network_range: Network range to scan
        """
        try:
            results = self.scanner.scan_network(network_range)
            GLib.idle_add(self.on_scan_completed, results)
        except Exception as e:
            GLib.idle_add(self.on_scan_error, str(e))

    def on_scan_progress(self, message: str, percentage: float) -> None:
        """
        Handle scan progress updates.

        Args:
            message: Progress message
            percentage: Progress percentage (0-100)
        """
        GLib.idle_add(self.loading_view.update_progress, message, percentage)

    def on_scan_completed(self, results: List[ScanResult]) -> None:
        """
        Handle scan completion.

        Args:
            results: Scan results
        """
        self.current_results = results
        self.results_view.display_results(results)

        # Switch to results view
        self.scanner_stack.set_visible_child_name("results")

    def on_scan_error(self, error_message: str) -> None:
        """
        Handle scan error.

        Args:
            error_message: Error message
        """
        self.show_error_dialog(_("Scan failed") + f": {error_message}")

        # Reset scanner state
        self.scanner = None
        self.scanning_thread = None

        # Return to welcome view
        self.scanner_stack.set_visible_child_name("welcome")

    def on_open_service(self, ip: str, service: ServiceInfo) -> None:
        """
        Handle opening a service.

        Args:
            ip: IP address
            service: Service information
        """
        try:
            if service.access_method == "http":
                url = f"http://{ip}:{service.port}"
                webbrowser.open(url)
            elif service.access_method == "https":
                url = f"https://{ip}:{service.port}"
                webbrowser.open(url)
            elif service.access_method == "ssh":
                # Show SSH username dialog
                self.show_ssh_dialog(ip, service.port)
            elif service.access_method == "smb":
                url = f"smb://{ip}"
                subprocess.Popen(
                    ["xdg-open", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif service.access_method == "ftp":
                url = f"ftp://{ip}:{service.port}"
                subprocess.Popen(
                    ["xdg-open", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif service.access_method == "sftp":
                # Show SFTP username dialog
                self.show_sftp_dialog(ip, service.port)
        except Exception as e:
            self.show_error_dialog(_("Failed to open service") + f": {e}")

    def show_error_dialog(self, message: str) -> None:
        """Show error dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self.window, heading=_("Error"), body=message
        )
        dialog.add_response("ok", _("OK"))
        dialog.show()

    def show_ssh_dialog(self, ip: str, port: int = 22) -> None:
        """
        Show SSH/SFTP connection dialog to get username and connection type.

        Args:
            ip: Target IP address
            port: SSH port (default 22)
        """
        # Create dialog
        dialog = Adw.MessageDialog.new(
            self.window, "SSH/SFTP Connection", f"Connect to {ip}:{port}"
        )
        dialog.set_modal(True)

        # Create content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)

        # Username entry
        username_label = Gtk.Label(label=_("Username:"))
        username_label.set_halign(Gtk.Align.START)
        content_box.append(username_label)

        username_entry = Gtk.Entry()
        username_entry.set_placeholder_text(_("Enter username (e.g., root, admin, pi)"))
        username_entry.set_text("root")  # Common default
        content_box.append(username_entry)

        # Connection type selection
        connection_label = Gtk.Label(label=_("Connection Type:"))
        connection_label.set_halign(Gtk.Align.START)
        connection_label.set_margin_top(8)
        content_box.append(connection_label)

        # Radio buttons for connection type
        ssh_radio = Gtk.CheckButton.new_with_label(
            _("SSH Terminal (command line access)")
        )
        sftp_radio = Gtk.CheckButton.new_with_label(
            _("SFTP Files (file manager access)")
        )
        sftp_radio.set_group(ssh_radio)
        ssh_radio.set_active(True)  # Default to SSH

        content_box.append(ssh_radio)
        content_box.append(sftp_radio)

        # Set the content
        dialog.set_extra_child(content_box)

        # Add buttons
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("connect", _("Connect"))
        dialog.set_response_appearance("connect", Adw.ResponseAppearance.SUGGESTED)

        # Handle response
        def on_response(dialog, response):
            if response == "connect":
                username = username_entry.get_text().strip()
                if not username:
                    username = "root"

                if ssh_radio.get_active():
                    self.open_ssh_terminal_with_user(ip, port, username)
                else:
                    self.open_sftp_with_user(ip, port, username)
            dialog.destroy()

        dialog.connect("response", on_response)

        # Focus the entry and select all text
        username_entry.grab_focus()
        username_entry.select_region(0, -1)

        dialog.present()

    def open_ssh_terminal_with_user(self, ip: str, port: int, username: str) -> None:
        """
        Open SSH connection in terminal with specified username.

        Args:
            ip: Target IP address
            port: SSH port
            username: SSH username
        """
        try:
            # Try different terminal emulators for SSH
            terminals = [
                ["ptyxis", "--", "ssh", f"{username}@{ip}", "-p", str(port)],
                ["tilix", "-e", "ssh", f"{username}@{ip}", "-p", str(port)],
                ["gnome-terminal", "--", "ssh", f"{username}@{ip}", "-p", str(port)],
                ["konsole", "-e", "ssh", f"{username}@{ip}", "-p", str(port)],
                ["xfce4-terminal", "-e", f"ssh {username}@{ip} -p {port}"],
                ["xterm", "-e", f"ssh {username}@{ip} -p {port}"],
            ]

            terminal_opened = False
            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(
                        terminal_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    terminal_opened = True
                    break
                except FileNotFoundError:
                    continue

            # If no terminal could be opened, try SFTP as fallback
            if not terminal_opened:
                url = f"sftp://{username}@{ip}:{port}"
                subprocess.Popen(
                    ["xdg-open", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            self.show_error_dialog(_("Failed to open SSH terminal") + f": {e}")

    def open_sftp_with_user(self, ip: str, port: int, username: str) -> None:
        """
        Open SFTP connection in file manager with specified username.

        Args:
            ip: Target IP address
            port: SFTP port
            username: SFTP username
        """
        try:
            # Construct SFTP URL
            if port == 22:
                sftp_url = f"sftp://{username}@{ip}"
            else:
                sftp_url = f"sftp://{username}@{ip}:{port}"

            # Try to open in file manager
            subprocess.Popen(
                ["xdg-open", sftp_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            self.show_error_dialog(_("Failed to open SFTP") + f": {e}")

    def on_welcome(self, action=None, param=None) -> None:
        """Show welcome screen."""
        WelcomeScreen.show_welcome(self.window, self.config_manager)

    def on_about(self, action=None, param=None) -> None:
        """Show about dialog."""
        about = Adw.AboutWindow(
            transient_for=self.window,
            application_name="Big Network Info",
            application_icon="big-network-info",
            developer_name=_("Network Tools"),
            version="1.0",
            copyright="© 2025 Network Tools",
            license_type=Gtk.License.GPL_2_0,
            comments=_("Network scanner with modern GTK4 interface"),
        )
        about.show()

    def on_quit(self, action=None, param=None) -> None:
        """Quit the application."""
        if self.scanner:
            self.scanner.stop_scan()
        self.quit()

    def on_scan_again(self) -> None:
        """Handle scan again button click from results view to restart scan with current settings."""
        # If we have a previous scan range, restart scan with it
        try:
            network_range = self.current_network_range
        except AttributeError:
            # Fallback to setup view if no prior range
            self.scanner_stack.set_visible_child_name("setup")
            return
        # Start a new scan using the existing configuration
        self.start_scan(network_range)

    def on_back_to_scan_setup(self) -> None:
        """Handle back button click from results view to return to scan setup."""
        self.scanner_stack.set_visible_child_name("setup")

    def on_scan_button_clicked(self, button: Gtk.Button) -> None:
        """Handle scan button click from welcome view."""
        network_range = self.range_row.get_text().strip()
        if not network_range:
            self.show_error_dialog(_("Please enter a network range to scan"))
            return

        # Start scanning in background thread (this will also switch to devices tab)
        self.start_scan(network_range)

    def _on_tab_clicked(self, button: Gtk.Button, tab_name: str) -> None:
        """Handle tab button clicks."""
        self.activate_tab(tab_name)

    def activate_tab(self, tab_name: str) -> None:
        """Switch to the specified tab and update button styling."""
        # Update button styling
        for name, button in self.tab_buttons.items():
            if name == tab_name:
                button.add_css_class("suggested-action")
            else:
                button.remove_css_class("suggested-action")

        # Handle WiFi monitoring based on tab selection
        if hasattr(self, "wifi_analyzer_view"):
            if tab_name == "wifi_analyzer":
                # Start WiFi monitoring when accessing WiFi tab
                self.wifi_analyzer_view.start_monitoring()
            else:
                # Optionally stop monitoring when leaving WiFi tab (for performance)
                # Comment the next line if you want monitoring to continue in background
                self.wifi_analyzer_view.stop_monitoring()

        # Switch content
        self.content_stack.set_visible_child_name(tab_name)
        self.current_tab = tab_name

    def create_diagnostics_tab_view(self) -> Gtk.Widget:
        """
        Create the dedicated diagnostics tab view.

        Returns:
            The diagnostics tab widget
        """
        # Create a stack for diagnostics views
        self.diagnostics_stack = Gtk.Stack()
        self.diagnostics_stack.set_transition_type(
            Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
        )
        self.diagnostics_stack.set_transition_duration(300)

        # Diagnostics welcome/start view
        diagnostics_welcome = self.create_diagnostics_welcome_view()
        self.diagnostics_stack.add_named(diagnostics_welcome, "welcome")

        # Diagnostics running/results view
        diagnostics_running = self.create_diagnostics_running_view()
        self.diagnostics_stack.add_named(diagnostics_running, "running")

        # Start with welcome view
        self.diagnostics_stack.set_visible_child_name("welcome")

        return self.diagnostics_stack

    def create_diagnostics_welcome_view(self) -> Gtk.Widget:
        """Create the diagnostics welcome page."""
        # Main container with vertical centering
        main_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_container.set_halign(Gtk.Align.FILL)
        main_container.set_valign(Gtk.Align.CENTER)
        main_container.set_margin_start(40)
        main_container.set_margin_end(40)
        main_container.set_margin_top(60)
        main_container.set_margin_bottom(60)

        # Header section with improved spacing and styling
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        header_box.set_halign(Gtk.Align.CENTER)
        header_box.set_margin_bottom(32)

        # Main icon
        main_icon = Gtk.Image.new_from_icon_name(
            "network-wireless-signal-excellent-symbolic"
        )
        main_icon.set_pixel_size(64)
        main_icon.add_css_class("accent")
        header_box.append(main_icon)

        # Subtitle with improved text
        subtitle_label = Gtk.Label(label=_("Quickly check network for common issues."))
        subtitle_label.add_css_class("title-4")
        subtitle_label.add_css_class("dim-label")
        subtitle_label.set_halign(Gtk.Align.CENTER)
        subtitle_label.set_justify(Gtk.Justification.CENTER)
        subtitle_label.set_wrap(True)
        subtitle_label.set_max_width_chars(60)
        header_box.append(subtitle_label)

        # Add header
        main_container.append(header_box)
        # Start Diagnostics button, centered and prominent
        start_btn = Gtk.Button(label=_("Start Diagnostics"))
        start_btn.add_css_class("suggested-action")
        start_btn.set_size_request(160, 40)
        start_btn.set_halign(Gtk.Align.CENTER)
        start_btn.connect("clicked", self.on_start_diagnostics)
        main_container.append(start_btn)
        return main_container

    def create_diagnostics_running_view(self) -> Gtk.Widget:
        """Create the diagnostics running/results view."""
        # Main container stacking content and footer
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.set_homogeneous(False)
        container.set_vexpand(True)

        # Main scrolled container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        # Main content container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(32)
        main_box.set_margin_bottom(24)
        scrolled.set_child(main_box)

        # Header section - well organized and clean
        header_section = self.create_diagnostics_header()
        main_box.append(header_section)

        # Progress section - separated from header
        progress_section = self.create_diagnostics_progress_section()
        main_box.append(progress_section)

        # Results section
        results_section = self.create_diagnostics_results_section()
        main_box.append(results_section)

        # Add the scrolled content to the container
        container.append(scrolled)

        # Separator between content and footer for visual clarity
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        container.append(separator)

        # Add persistent footer
        footer = self.create_diagnostics_footer()
        container.append(footer)

        return container

    def create_diagnostics_header(self) -> Gtk.Widget:
        """Create a clean, organized header section."""
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        header_box.set_halign(Gtk.Align.CENTER)

        # Subtitle - shown during diagnostics
        self.subtitle_label = Gtk.Label(
            label=_("Analyzing your network connection step by step")
        )
        self.subtitle_label.add_css_class("title-4")
        self.subtitle_label.add_css_class("dim-label")
        self.subtitle_label.set_justify(Gtk.Justification.CENTER)
        self.subtitle_label.set_halign(Gtk.Align.CENTER)
        header_box.append(self.subtitle_label)

        # Summary banner - shown after completion
        self.summary_label = Gtk.Label()
        self.summary_label.set_halign(Gtk.Align.CENTER)
        self.summary_label.add_css_class("title-4")
        self.summary_label.set_wrap(True)
        self.summary_label.set_justify(Gtk.Justification.CENTER)
        self.summary_label.set_visible(False)
        header_box.append(self.summary_label)

        return header_box

    def create_diagnostics_progress_section(self) -> Gtk.Widget:
        """Create a clean progress section."""
        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        progress_box.set_halign(Gtk.Align.CENTER)

        # Progress bar container
        progress_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        progress_container.set_halign(Gtk.Align.CENTER)

        self.diagnostics_progress = Gtk.ProgressBar()
        self.diagnostics_progress.set_size_request(300, -1)
        self.diagnostics_progress.set_show_text(True)
        self.diagnostics_progress.set_text("0 %")
        self.diagnostics_progress.set_fraction(0.0)
        progress_container.append(self.diagnostics_progress)

        progress_box.append(progress_container)

        # Status section with spinner
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_box.set_halign(Gtk.Align.CENTER)

        # Spinner for running diagnostics
        self.diagnostics_spinner = Gtk.Spinner()
        self.diagnostics_spinner.set_size_request(16, 16)
        self.diagnostics_spinner.set_visible(False)
        status_box.append(self.diagnostics_spinner)

        # Status text
        self.progress_status_label = Gtk.Label(label=_("Preparing diagnostics..."))
        self.progress_status_label.add_css_class("dim-label")
        self.progress_status_label.set_halign(Gtk.Align.CENTER)
        status_box.append(self.progress_status_label)

        progress_box.append(status_box)

        return progress_box

    def create_diagnostics_results_section(self) -> Gtk.Widget:
        """Create the diagnostics results section."""
        # Diagnostics steps container
        self.diagnostics_group = Adw.PreferencesGroup()
        return self.diagnostics_group

    def create_diagnostics_footer(self) -> Gtk.Widget:
        """Create a fixed footer for diagnostic action buttons that matches the header style."""
        # Footer container always visible at bottom, styled like header
        footer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        footer_box.set_valign(Gtk.Align.END)
        footer_box.set_halign(Gtk.Align.FILL)
        footer_box.set_margin_start(24)
        footer_box.set_margin_end(24)
        footer_box.set_margin_top(8)
        footer_box.set_margin_bottom(8)

        # Button container
        button_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        button_container.set_halign(Gtk.Align.CENTER)

        # Back button
        back_button = Gtk.Button(label=_("← Back"))
        back_button.connect("clicked", self.on_back_to_diagnostics_welcome)
        button_container.append(back_button)

        # Copy All Results button
        self.copy_diagnostics_button = Gtk.Button(label=_("Copy All"))
        self.copy_diagnostics_button.connect("clicked", self.on_copy_all_diagnostics)
        self.copy_diagnostics_button.set_valign(Gtk.Align.CENTER)
        self.copy_diagnostics_button.set_sensitive(False)
        button_container.append(self.copy_diagnostics_button)

        # Export PDF button
        self.export_diagnostics_button = Gtk.Button(label=_("Export PDF"))
        self.export_diagnostics_button.connect(
            "clicked", self.on_export_diagnostics_pdf
        )
        self.export_diagnostics_button.set_valign(Gtk.Align.CENTER)
        self.export_diagnostics_button.set_sensitive(False)
        button_container.append(self.export_diagnostics_button)

        # Run again button
        self.run_again_button = Gtk.Button(label=_("Run Again"))
        self.run_again_button.add_css_class("suggested-action")
        self.run_again_button.connect("clicked", self.on_run_diagnostics_again)
        self.run_again_button.set_valign(Gtk.Align.CENTER)
        self.run_again_button.set_sensitive(False)
        button_container.append(self.run_again_button)

        footer_box.append(button_container)
        return footer_box

    def create_scanner_tab_view(self) -> Gtk.Widget:
        """
        Create the dedicated scanner tab view for device discovery.

        Returns:
            The scanner tab widget
        """
        # Create a stack to switch between scan setup and results
        self.scanner_stack = Gtk.Stack()
        self.scanner_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.scanner_stack.set_transition_duration(300)

        # Scan Setup View
        scan_setup_view = self.create_scan_setup_view()
        self.scanner_stack.add_named(scan_setup_view, "setup")

        # Results View
        self.results_view = ScanResultsView(
            self.on_open_service,
            self.on_scan_again,
            self.on_export_pdf,
            self.on_back_to_scan_setup,
        )
        self.scanner_stack.add_named(self.results_view, "results")

        # Scanning View (integrated loading)
        scanning_view = self.create_scanning_view()
        self.scanner_stack.add_named(scanning_view, "scanning")

        # Start with setup view
        self.scanner_stack.set_visible_child_name("setup")

        return self.scanner_stack

    def create_scan_setup_view(self) -> Gtk.Widget:
        """Create the network scan setup page with centered layout."""
        # Main container centered vertically
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        container.set_valign(Gtk.Align.CENTER)
        container.set_halign(Gtk.Align.FILL)
        container.set_margin_start(40)
        container.set_margin_end(40)
        container.set_margin_top(60)
        container.set_margin_bottom(60)

        # Header section
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        header_box.set_halign(Gtk.Align.CENTER)
        # Icon
        icon = Gtk.Image.new_from_icon_name("network-workgroup-symbolic")
        icon.set_pixel_size(64)
        icon.add_css_class("accent")
        header_box.append(icon)
        # Subtitle
        subtitle = Gtk.Label(label=_("Scan your network to find devices and services."))
        subtitle.add_css_class("title-4")
        subtitle.add_css_class("dim-label")
        subtitle.set_wrap(True)
        subtitle.set_justify(Gtk.Justification.CENTER)
        header_box.append(subtitle)
        container.append(header_box)

        # Input for network range
        self.range_row = Adw.EntryRow()
        self.range_row.set_title(_("Network Range"))

        # Auto-detect network range on startup
        if not self.scanner:
            self.scanner = NetworkScanner(config_manager=self.config_manager)
        detected_range = self.scanner.get_local_network_range()
        self.range_row.set_text(detected_range)

        self.range_row.set_show_apply_button(False)
        # Highlight entry in a card and center it with constrained width
        self.range_row.add_css_class("card")
        self.range_row.set_halign(Gtk.Align.CENTER)
        self.range_row.set_size_request(360, -1)
        auto_btn = Gtk.Button()
        auto_btn.set_icon_name("find-location-symbolic")
        auto_btn.add_css_class("flat")
        auto_btn.connect("clicked", self.on_auto_detect)
        self.range_row.add_suffix(auto_btn)
        container.append(self.range_row)

        # Action button
        action_btn = Gtk.Button(label=_("Start Scan"))
        action_btn.add_css_class("suggested-action")
        action_btn.set_size_request(160, 40)
        action_btn.set_halign(Gtk.Align.CENTER)
        action_btn.connect("clicked", self.on_scan_button_clicked)
        container.append(action_btn)

        return container

    def create_scanning_view(self) -> Gtk.Widget:
        """Create an integrated scanning view that fills the space."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_spacing(0)
        main_box.set_halign(Gtk.Align.FILL)
        main_box.set_valign(Gtk.Align.FILL)

        # Top spacer
        top_spacer = Gtk.Box()
        top_spacer.set_vexpand(True)
        main_box.append(top_spacer)

        # Scanning content container
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content_box.set_halign(Gtk.Align.CENTER)
        content_box.set_margin_start(60)
        content_box.set_margin_end(60)
        main_box.append(content_box)

        # Loading view
        self.loading_view = LoadingView()
        content_box.append(self.loading_view)

        # Bottom spacer
        bottom_spacer = Gtk.Box()
        bottom_spacer.set_vexpand(True)
        main_box.append(bottom_spacer)

        return main_box

    def create_combined_settings_view(self) -> Gtk.Widget:
        """
        Create settings view with integrated custom service management.

        Returns:
            The settings view widget
        """
        from .config_view import ConfigurationView

        # Just return the configuration view directly - no extra settings
        config_view = ConfigurationView(self.window, self.config_manager)
        return config_view

    def run_network_diagnostics(self) -> None:
        """Run network diagnostics and update the UI in real-time."""
        # Clear previous results completely
        self.clear_diagnostics_steps()

        # Reset progress bar to 0
        self.diagnostics_progress.set_fraction(0.0)
        self.run_again_button.set_sensitive(False)
        self.export_diagnostics_button.set_sensitive(False)

        # Reset progress status label
        if hasattr(self, "progress_status_label"):
            self.progress_status_label.set_text("Preparing diagnostics...")
            self.progress_status_label.remove_css_class("success")
            self.progress_status_label.remove_css_class("warning")
            self.progress_status_label.remove_css_class("error")
            self.progress_status_label.add_css_class("dim-label")

        # Hide spinner initially
        if hasattr(self, "diagnostics_spinner"):
            self.diagnostics_spinner.stop()
            self.diagnostics_spinner.set_visible(False)
        # Restore subtitle and hide previous summary
        if hasattr(self, "subtitle_label"):
            self.subtitle_label.set_visible(True)
        if hasattr(self, "summary_label"):
            self.summary_label.set_visible(False)

        # Initialize fresh diagnostics instance and clear previous step_rows
        self.diagnostics = NetworkDiagnostics()

        # Create step rows first (before running diagnostics)
        self.create_diagnostic_step_rows()

        # Run diagnostics with proper callback parameters
        self.diagnostics.run_diagnostics(
            progress_callback=self.on_diagnostic_step_update,
            completion_callback=self.on_diagnostics_complete,
        )

    def clear_diagnostics_steps(self) -> None:
        """Clear all previously created diagnostic step rows and reset the diagnostics group description."""
        # Remove only the rows we previously added
        if hasattr(self, "step_rows"):
            for row in self.step_rows.values():
                self.diagnostics_group.remove(row)
            self.step_rows.clear()

    def create_diagnostic_step_rows(self) -> None:
        """Create rows for each diagnostic step."""
        self.step_rows = {}

        # Ensure we have diagnostic steps
        if not hasattr(self.diagnostics, "steps") or not self.diagnostics.steps:
            self.diagnostics.steps = self.diagnostics.create_diagnostic_steps()

        for i, step in enumerate(self.diagnostics.steps):
            # Compact action row for each step
            row = Adw.ActionRow()
            row.add_css_class("compact")
            row.set_title(step.name)
            row.set_subtitle(step.description)

            # Status icon
            status_icon = Gtk.Image.new_from_icon_name("content-loading-symbolic")
            status_icon.add_css_class("dim-label")
            row.add_prefix(status_icon)

            # Container for status label and copy button
            suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            suffix_box.set_valign(Gtk.Align.CENTER)

            # Status label
            status_label = Gtk.Label(label=_("Waiting..."))
            status_label.add_css_class("caption")
            status_label.add_css_class("dim-label")
            status_label.set_valign(Gtk.Align.CENTER)
            suffix_box.append(status_label)

            # Copy button for step details (initially hidden)
            copy_button = Gtk.Button()
            copy_button.set_icon_name("edit-copy-symbolic")
            copy_button.set_tooltip_text(_("Copy step details"))
            copy_button.add_css_class("flat")
            copy_button.set_valign(Gtk.Align.CENTER)
            copy_button.set_visible(False)  # Initially hidden
            copy_button.connect(
                "clicked",
                lambda btn, step_index=i: self.copy_step_details_by_index(step_index),
            )
            suffix_box.append(copy_button)

            row.add_suffix(suffix_box)

            # Store references for updating
            row.status_icon = status_icon
            row.status_label = status_label
            row.copy_button = copy_button
            row.step = step

            self.step_rows[i] = row
            self.diagnostics_group.add(row)

    def on_diagnostic_step_update(self, step: DiagnosticStep) -> None:
        """Handle diagnostic step update (called from background thread)."""
        GLib.idle_add(self.update_diagnostic_step_ui, step)

    def update_diagnostic_step_ui(self, step: DiagnosticStep) -> None:
        """Update the UI for a diagnostic step (runs on main thread)."""
        # Find the step index
        step_index = None
        for i, s in enumerate(self.diagnostics.steps):
            if s.name == step.name:
                step_index = i
                break

        if step_index is None or step_index not in self.step_rows:
            return

        row = self.step_rows[step_index]

        # Update progress status label and spinner
        if hasattr(self, "progress_status_label"):
            # Count currently running steps
            running_steps = [
                s
                for s in self.diagnostics.steps
                if s.status == DiagnosticStatus.RUNNING
            ]

            if step.status == DiagnosticStatus.RUNNING:
                if len(running_steps) == 1:
                    self.progress_status_label.set_text(_("Running: ") + step.name)
                else:
                    self.progress_status_label.set_text(
                        _("Running: ") + str(len(running_steps)) + " " + _("tests")
                    )
                # Show and start spinner when a step is running
                if hasattr(self, "diagnostics_spinner"):
                    self.diagnostics_spinner.set_visible(True)
                    self.diagnostics_spinner.start()
            elif step.status == DiagnosticStatus.PASSED:
                if len(running_steps) == 0:
                    self.progress_status_label.set_text(_("Completed: ") + step.name)
                else:
                    if len(running_steps) == 1:
                        self.progress_status_label.set_text(
                            _("Running: ") + running_steps[0].name
                        )
                    else:
                        self.progress_status_label.set_text(
                            _("Running: ") + str(len(running_steps)) + " " + _("tests")
                        )
            elif step.status == DiagnosticStatus.FAILED:
                if len(running_steps) == 0:
                    self.progress_status_label.set_text(_("Failed: ") + step.name)
                else:
                    if len(running_steps) == 1:
                        self.progress_status_label.set_text(
                            _("Running: ") + running_steps[0].name
                        )
                    else:
                        self.progress_status_label.set_text(
                            _("Running: ") + str(len(running_steps)) + " " + _("tests")
                        )

        # Update status icon and label based on step status
        if step.status == DiagnosticStatus.RUNNING:
            row.status_icon.set_from_icon_name("content-loading-symbolic")
            row.status_icon.remove_css_class("success")
            row.status_icon.remove_css_class("error")
            row.status_icon.remove_css_class("warning")
            row.status_icon.add_css_class("accent")
            row.status_label.set_text(_("Running..."))
            row.status_label.remove_css_class("success")
            row.status_label.remove_css_class("error")
            row.status_label.remove_css_class("warning")
            row.status_label.add_css_class("accent")

        elif step.status == DiagnosticStatus.PASSED:
            row.status_icon.set_from_icon_name("emblem-ok-symbolic")
            row.status_icon.remove_css_class("accent")
            row.status_icon.remove_css_class("error")
            row.status_icon.remove_css_class("warning")
            row.status_icon.add_css_class("success")
            row.status_label.set_text("")  # Remove text for passed tests
            row.status_label.remove_css_class("accent")
            row.status_label.remove_css_class("error")
            row.status_label.remove_css_class("warning")
            row.status_label.add_css_class("success")

        elif step.status == DiagnosticStatus.FAILED:
            row.status_icon.set_from_icon_name("dialog-error-symbolic")
            row.status_icon.remove_css_class("accent")
            row.status_icon.remove_css_class("success")
            row.status_icon.remove_css_class("warning")
            row.status_icon.add_css_class("error")
            row.status_label.set_text(_("✗ Failed"))
            row.status_label.remove_css_class("accent")
            row.status_label.remove_css_class("success")
            row.status_label.remove_css_class("warning")
            row.status_label.add_css_class("error")

        elif step.status == DiagnosticStatus.WARNING:
            row.status_icon.set_from_icon_name("dialog-warning-symbolic")
            row.status_icon.remove_css_class("accent")
            row.status_icon.remove_css_class("success")
            row.status_icon.remove_css_class("error")
            row.status_icon.add_css_class("warning")
            row.status_label.set_text(_("⚠ Warning"))
            row.status_label.remove_css_class("accent")
            row.status_label.remove_css_class("success")
            row.status_label.remove_css_class("error")
            row.status_label.add_css_class("warning")

        # Update subtitle with details or troubleshooting tip
        if step.details:
            row.set_subtitle(f"{step.description} • {step.details}")
        elif step.troubleshooting_tip and step.status == DiagnosticStatus.FAILED:
            row.set_subtitle(f"{step.description} • {step.troubleshooting_tip}")

        # Show/hide copy button based on whether there are details to copy
        if hasattr(row, "copy_button"):
            if step.details and step.status in [
                DiagnosticStatus.PASSED,
                DiagnosticStatus.FAILED,
                DiagnosticStatus.WARNING,
            ]:
                row.copy_button.set_visible(True)
            else:
                row.copy_button.set_visible(False)

        # Update progress bar based on completed steps
        completed_steps = sum(
            1
            for s in self.diagnostics.steps
            if s.status
            in [
                DiagnosticStatus.PASSED,
                DiagnosticStatus.FAILED,
                DiagnosticStatus.WARNING,
            ]
        )
        progress = completed_steps / len(self.diagnostics.steps)
        self.diagnostics_progress.set_fraction(progress)
        # Display percentage text
        if self.diagnostics_progress.get_show_text():
            pct = int(progress * 100)
            self.diagnostics_progress.set_text(f"{pct} %")

    def on_diagnostics_complete(self, steps: List[DiagnosticStep]) -> None:
        """Handle diagnostics completion (called from background thread)."""
        GLib.idle_add(self.update_diagnostics_complete_ui, steps)

    def update_diagnostics_complete_ui(self, steps: List[DiagnosticStep]) -> None:
        """Update UI when diagnostics are complete (runs on main thread)."""
        # Hide and stop spinner when diagnostics complete
        if hasattr(self, "diagnostics_spinner"):
            self.diagnostics_spinner.stop()
            self.diagnostics_spinner.set_visible(False)

        # Finalize progress bar
        self.diagnostics_progress.set_fraction(1.0)
        if self.diagnostics_progress.get_show_text():
            self.diagnostics_progress.set_text("100 %")
        # Hide subtitle after completion
        if hasattr(self, "subtitle_label"):
            self.subtitle_label.set_visible(False)
        # Enable Run Again and Export buttons
        self.run_again_button.set_sensitive(True)
        self.export_diagnostics_button.set_sensitive(True)
        self.copy_diagnostics_button.set_sensitive(True)

        # Count results
        failed = sum(1 for step in steps if step.status == DiagnosticStatus.FAILED)
        warnings = sum(1 for step in steps if step.status == DiagnosticStatus.WARNING)

        # Update progress status label
        if hasattr(self, "progress_status_label"):
            if failed == 0 and warnings == 0:
                self.progress_status_label.set_text(
                    _("✓ All diagnostics completed successfully!")
                )
                self.progress_status_label.remove_css_class("dim-label")
                self.progress_status_label.add_css_class("success")
            elif failed == 0:
                self.progress_status_label.set_text(
                    _("✓ Completed with ") + f"{warnings} " + _("warning(s)")
                )
                self.progress_status_label.remove_css_class("dim-label")
                self.progress_status_label.add_css_class("warning")
            else:
                self.progress_status_label.set_text(
                    _("✗ Completed with") + f" {failed} " + _("failure(s)")
                )
                self.progress_status_label.remove_css_class("dim-label")
                self.progress_status_label.add_css_class("error")

        # Show simple summary for users
        if hasattr(self, "summary_label"):
            # Clear previous status classes
            for cls in ("dim-label", "success", "warning", "error"):
                self.summary_label.remove_css_class(cls)
            # Set text and color according to result
            if failed == 0 and warnings == 0:
                self.summary_label.set_text(
                    _("All checks passed! Your network is healthy 😊")
                )
                self.summary_label.add_css_class("success")
            elif failed == 0:
                self.summary_label.set_text(
                    _("Completed with ")
                    + f"{warnings} "
                    + _("warning(s). Network looks okay.")
                )
                self.summary_label.add_css_class("warning")
            else:
                self.summary_label.set_text(
                    str(failed) + " " + _("issue(s) detected. Review steps below.")
                )
                self.summary_label.add_css_class("error")
            self.summary_label.set_visible(True)

    def on_run_diagnostics_again(self, button: Gtk.Button) -> None:
        """Handle run diagnostics again button click."""
        self.run_network_diagnostics()

    def on_export_pdf(self, results: List[ScanResult]) -> None:
        """Handle PDF export request from results view."""
        try:
            # Create PDF exporter
            exporter = PDFExporter()

            # Use native file chooser via portal
            from gi.repository import Gio

            # Get default filename
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            default_filename = f"network_scan_report_{timestamp}.pdf"

            # Create file dialog
            dialog = Gtk.FileDialog()
            dialog.set_title(_("Save PDF Report"))
            dialog.set_initial_name(default_filename)

            # Set file filter for PDF files
            filter_list = Gio.ListStore.new(Gtk.FileFilter)
            pdf_filter = Gtk.FileFilter()
            pdf_filter.set_name(_("PDF files"))
            pdf_filter.add_pattern("*.pdf")
            filter_list.append(pdf_filter)
            dialog.set_filters(filter_list)
            dialog.set_default_filter(pdf_filter)

            # Show save dialog asynchronously
            dialog.save(
                self.window, None, self._on_save_dialog_complete, (exporter, results)
            )

        except Exception as e:
            self.show_error_dialog(_("Failed to export PDF") + f": {str(e)}")

    def _on_save_dialog_complete(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, user_data
    ) -> None:
        """Handle save dialog completion."""
        exporter, results = user_data

        try:
            # Get the selected file
            file = dialog.save_finish(result)
            if file:
                file_path = file.get_path()
                try:
                    # Export to PDF with network range information
                    network_range = getattr(self, "current_network_range", _("Unknown"))
                    generated_path = exporter.export_to_pdf(
                        results, file_path, network_range
                    )

                    # Show success message
                    success_dialog = Adw.MessageDialog.new(
                        self.window,
                        _("Export Successful"),
                        _("PDF report saved to") + f":\n{generated_path}",
                    )
                    success_dialog.add_response("ok", _("OK"))
                    success_dialog.add_response("open", _("Open File"))
                    success_dialog.set_response_appearance(
                        "open", Adw.ResponseAppearance.SUGGESTED
                    )
                    success_dialog.connect(
                        "response", self._on_pdf_success_response, generated_path
                    )
                    success_dialog.present()

                except Exception as e:
                    self.show_error_dialog(_("Failed to save PDF") + f": {str(e)}")

        except Exception as e:
            # User cancelled or error occurred - silently ignore cancellation
            if "cancelled" not in str(e).lower():
                self.show_error_dialog(_("Failed to save file") + f": {str(e)}")

    def _on_pdf_success_response(
        self, dialog: Adw.MessageDialog, response: str, file_path: str
    ) -> None:
        """Handle PDF export success dialog response."""
        if response == "open":
            try:
                # Try to open the PDF with the default application
                subprocess.run(["xdg-open", file_path], check=True)
            except Exception as e:
                self.show_error_dialog(_("Failed to open PDF") + f": {str(e)}")
        dialog.destroy()

    def on_export_diagnostics_pdf(self, button: Gtk.Button) -> None:
        """Handle diagnostics PDF export button click."""
        if (
            not hasattr(self, "diagnostics")
            or not self.diagnostics
            or not self.diagnostics.steps
        ):
            self.show_error_dialog(_("No diagnostics results to export"))
            return

        try:
            # Create PDF exporter
            exporter = PDFExporter()

            # Use native file chooser via portal
            from gi.repository import Gio

            # Get default filename
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            default_filename = f"network_diagnostics_report_{timestamp}.pdf"

            # Create file dialog
            dialog = Gtk.FileDialog()
            dialog.set_title(_("Save Diagnostics PDF Report"))
            dialog.set_initial_name(default_filename)

            # Set file filter for PDF files
            filter_list = Gio.ListStore.new(Gtk.FileFilter)
            pdf_filter = Gtk.FileFilter()
            pdf_filter.set_name("PDF files")
            pdf_filter.add_pattern("*.pdf")
            filter_list.append(pdf_filter)
            dialog.set_filters(filter_list)
            dialog.set_default_filter(pdf_filter)

            # Show save dialog asynchronously
            dialog.save(
                self.window,
                None,
                self._on_diagnostics_save_dialog_complete,
                (exporter, self.diagnostics.steps),
            )

        except Exception as e:
            self.show_error_dialog(_("Failed to export diagnostics PDF: ") + str(e))

    def _on_diagnostics_save_dialog_complete(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, user_data
    ) -> None:
        """Handle diagnostics save dialog completion."""
        exporter, steps = user_data

        try:
            # Get the selected file
            file = dialog.save_finish(result)
            if file:
                file_path = file.get_path()
                try:
                    # Export diagnostics to PDF
                    generated_path = exporter.export_diagnostics_to_pdf(
                        steps, file_path
                    )

                    # Show success message
                    success_dialog = Adw.MessageDialog.new(
                        self.window,
                        _("Export Successful"),
                        _("Diagnostics report saved to:") + f"\n{generated_path}",
                    )
                    success_dialog.add_response("ok", _("OK"))
                    success_dialog.add_response("open", _("Open File"))
                    success_dialog.set_response_appearance(
                        "open", Adw.ResponseAppearance.SUGGESTED
                    )
                    success_dialog.connect(
                        "response", self._on_pdf_success_response, generated_path
                    )
                    success_dialog.present()

                except Exception as e:
                    self.show_error_dialog(
                        _("Failed to save diagnostics PDF: ") + str(e)
                    )

        except Exception as e:
            # User cancelled or error occurred - silently ignore cancellation
            if "cancelled" not in str(e).lower():
                self.show_error_dialog(_("Failed to save file: ") + str(e))

    def _on_window_destroy(self, window) -> None:
        """Handle window destruction and cleanup resources"""
        if hasattr(self, "wifi_analyzer_view") and self.wifi_analyzer_view:
            self.wifi_analyzer_view.cleanup()

    def copy_to_clipboard(self, text: str) -> None:
        """
        Copy text to clipboard with user feedback.

        Args:
            text: Text to copy to clipboard
        """
        print(f"copy_to_clipboard called with text length: {len(text)}")
        print(f"Text preview: {text[:200]}...")

        try:
            display = Gdk.Display.get_default()
            if display is None:
                print("No default display found")
                return

            clipboard = display.get_clipboard()
            if clipboard is None:
                print("No clipboard found")
                return

            # Use the correct GTK4 clipboard API
            clipboard.set(text)
            print(f"Successfully copied {len(text)} characters to clipboard")
        except Exception as e:
            print(f"Failed to copy to clipboard: {e}")
            import traceback

            traceback.print_exc()

    def get_diagnostic_results_text(self) -> str:
        """
        Generate a comprehensive text summary of all diagnostic results.

        Returns:
            Formatted text string containing all diagnostic results
        """
        if not hasattr(self, "diagnostics") or not self.diagnostics.steps:
            return ""

        lines = []
        lines.append("=== NETWORK DIAGNOSTICS RESULTS ===")
        lines.append("")

        for step in self.diagnostics.steps:
            status_text = {
                DiagnosticStatus.PASSED: "✓ PASSED",
                DiagnosticStatus.FAILED: "✗ FAILED",
                DiagnosticStatus.WARNING: "⚠ WARNING",
                DiagnosticStatus.RUNNING: "⟳ RUNNING",
                DiagnosticStatus.PENDING: "⋯ PENDING",
            }.get(step.status, "UNKNOWN")

            lines.append(f"{step.name}: {status_text}")
            if step.description:
                lines.append(f"  Description: {step.description}")
            if step.details:
                lines.append(f"  Details: {step.details}")
            if step.troubleshooting_tip and step.status == DiagnosticStatus.FAILED:
                lines.append(f"  Troubleshooting: {step.troubleshooting_tip}")
            if step.duration_ms > 0:
                lines.append(f"  Duration: {step.duration_ms}ms")
            lines.append("")

        # Summary
        passed = sum(
            1 for s in self.diagnostics.steps if s.status == DiagnosticStatus.PASSED
        )
        failed = sum(
            1 for s in self.diagnostics.steps if s.status == DiagnosticStatus.FAILED
        )
        warnings = sum(
            1 for s in self.diagnostics.steps if s.status == DiagnosticStatus.WARNING
        )

        lines.append("=== SUMMARY ===")
        lines.append(f"Passed: {passed}")
        lines.append(f"Failed: {failed}")
        lines.append(f"Warnings: {warnings}")

        return "\n".join(lines)

    def copy_step_details_by_index(self, step_index: int) -> None:
        """
        Copy the details of a specific diagnostic step to clipboard by index.

        Args:
            step_index: Index of the diagnostic step to copy details from
        """
        if not hasattr(self, "diagnostics") or not self.diagnostics.steps:
            print("No diagnostics steps available")
            return

        if step_index >= len(self.diagnostics.steps):
            print(f"Invalid step index: {step_index}")
            return

        step = self.diagnostics.steps[step_index]
        print(
            f"Copying details for step: {step.name}, status: {step.status}, details: {step.details}"
        )

        if not step.details:
            print("No details available for this step")
            return

        status_text = {
            DiagnosticStatus.PASSED: "✓ PASSED",
            DiagnosticStatus.FAILED: "✗ FAILED",
            DiagnosticStatus.WARNING: "⚠ WARNING",
            DiagnosticStatus.RUNNING: "⟳ RUNNING",
            DiagnosticStatus.PENDING: "⋯ PENDING",
        }.get(step.status, "UNKNOWN")

        details_text = f"{step.name}: {status_text}\n"
        details_text += f"Description: {step.description}\n"
        details_text += f"Details: {step.details}"

        if step.troubleshooting_tip and step.status == DiagnosticStatus.FAILED:
            details_text += f"\nTroubleshooting: {step.troubleshooting_tip}"

        if step.duration_ms > 0:
            details_text += f"\nDuration: {step.duration_ms}ms"

        print(f"Copying text: {details_text[:100]}...")
        self.copy_to_clipboard(details_text)

    def copy_step_details(self, step: DiagnosticStep) -> None:
        """
        Copy the details of a specific diagnostic step to clipboard.

        Args:
            step: The diagnostic step to copy details from
        """
        if not step.details:
            return

        status_text = {
            DiagnosticStatus.PASSED: "✓ PASSED",
            DiagnosticStatus.FAILED: "✗ FAILED",
            DiagnosticStatus.WARNING: "⚠ WARNING",
            DiagnosticStatus.RUNNING: "⟳ RUNNING",
            DiagnosticStatus.PENDING: "⋯ PENDING",
        }.get(step.status, "UNKNOWN")

        details_text = f"{step.name}: {status_text}\n"
        details_text += f"Description: {step.description}\n"
        details_text += f"Details: {step.details}"

        if step.troubleshooting_tip and step.status == DiagnosticStatus.FAILED:
            details_text += f"\nTroubleshooting: {step.troubleshooting_tip}"

        if step.duration_ms > 0:
            details_text += f"\nDuration: {step.duration_ms}ms"

        self.copy_to_clipboard(details_text)

    def on_copy_all_diagnostics(self, button: Gtk.Button) -> None:
        """Handle copying all diagnostic results to clipboard."""
        print("Copy All Diagnostics button clicked")
        results_text = self.get_diagnostic_results_text()
        print(
            f"Generated results text length: {len(results_text) if results_text else 0}"
        )
        if results_text:
            self.copy_to_clipboard(results_text)
        else:
            print("No results text generated")
