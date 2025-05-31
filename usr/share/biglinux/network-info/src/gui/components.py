"""
GUI components for the network scanner application.
Contains results view, loading view, and settings view.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from gi.repository import Gtk, Adw, Gdk, Gio, GLib
from .translation import _
from typing import List, Callable, Optional
import subprocess
import threading

from ..core.scanner import ScanResult
from ..core.services import ServiceInfo
from ..utils.network import is_local_ip


class LoadingView(Gtk.Box):
    """Loading view with animated progress indicator."""

    def __init__(self):
        """Initialize the loading view."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_margin_start(50)
        self.set_margin_end(50)
        self.set_margin_top(50)
        self.set_margin_bottom(50)

        # Create spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(64, 64)
        self.spinner.start()
        self.append(self.spinner)

        # Create progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_size_request(300, -1)
        self.progress_bar.set_show_text(True)
        self.append(self.progress_bar)

        # Create status label
        self.status_label = Gtk.Label(label=_("Initializing scan..."))
        self.status_label.add_css_class("title-4")
        self.append(self.status_label)

        # Create subtitle
        subtitle = Gtk.Label(
            label=_("Please wait while we discover devices on your network")
        )
        subtitle.add_css_class("dim-label")
        self.append(subtitle)

    def update_progress(self, message: str, percentage: float) -> None:
        """
        Update the loading progress.

        Args:
            message: Status message
            percentage: Progress percentage (0-100)
        """
        self.status_label.set_text(message)
        self.progress_bar.set_fraction(percentage / 100.0)
        self.progress_bar.set_text(f"{percentage:.1f}%")


class ScanResultsView(Gtk.Box):
    """View for displaying scan results in a modern interface."""

    def __init__(
        self,
        open_service_callback: Callable[[str, ServiceInfo], None],
        scan_again_callback: Optional[Callable[[], None]] = None,
        export_pdf_callback: Optional[Callable[[List[ScanResult]], None]] = None,
        back_callback: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the results view with a fixed footer layout.
        """
        # Vertical box as main container
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.open_service_callback = open_service_callback
        self.scan_again_callback = scan_again_callback
        self.export_pdf_callback = export_pdf_callback
        self.back_callback = back_callback
        self.current_results: List[ScanResult] = []

        # Scrolled area for dynamic content (welcome/results)
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_vexpand(True)
        # Content box inside scrolled window
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.main_box.set_margin_start(12)
        self.main_box.set_margin_end(12)
        self.main_box.set_margin_top(12)
        self.main_box.set_margin_bottom(12)
        self.scrolled.set_child(self.main_box)
        self.append(self.scrolled)

        # Create welcome message (shown when no results)
        self.welcome_box = self.create_welcome_view()
        self.main_box.append(self.welcome_box)

        # Results container (hidden initially)
        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.results_box.set_visible(False)
        self.main_box.append(self.results_box)

        # Separator between content and footer for visual clarity (matches diagnostics)
        self.footer_separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.footer_separator.set_visible(False)
        self.append(self.footer_separator)

        # Footer (always below scrolled content)
        self.footer_box = self.create_results_footer()
        self.footer_separator.set_visible(False)
        self.footer_box.set_visible(False)
        self.append(self.footer_box)

    def create_welcome_view(self) -> Gtk.Box:
        """Create the welcome view shown when no results are available."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_start(50)
        box.set_margin_end(50)
        box.set_margin_top(100)
        box.set_margin_bottom(100)

        # Icon
        icon = Gtk.Image.new_from_icon_name("network-workgroup")
        icon.set_pixel_size(128)
        icon.add_css_class("dim-label")
        box.append(icon)

        # Title
        title = Gtk.Label(label="Big Network Info")
        title.add_css_class("title-1")
        box.append(title)

        # Subtitle
        subtitle = Gtk.Label(
            label=_(
                "Discover devices and services on your network\n"
                "Click 'Start Scan' to begin scanning your local network"
            )
        )
        subtitle.add_css_class("title-4")
        subtitle.add_css_class("dim-label")
        subtitle.set_justify(Gtk.Justification.CENTER)
        box.append(subtitle)

        return box

    def display_results(self, results: List[ScanResult]) -> None:
        """
        Display scan results with improved sorting and gateway identification.

        Args:
            results: List of scan results to display
        """
        # Store results for export functionality
        self.current_results = results

        # Clear previous results
        while self.results_box.get_first_child():
            self.results_box.remove(self.results_box.get_first_child())

        # Hide welcome view and show results
        self.welcome_box.set_visible(False)
        self.results_box.set_visible(True)
        # Show footer and separator when results are displayed
        self.footer_separator.set_visible(True)
        self.footer_box.set_visible(True)

        if not results:
            # No results found - still show scan again button
            no_results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
            no_results_box.set_valign(Gtk.Align.CENTER)
            no_results_box.set_halign(Gtk.Align.CENTER)
            no_results_box.set_margin_top(100)
            no_results_box.set_margin_bottom(100)

            # Create icon and message
            icon = Gtk.Image.new_from_icon_name("network-offline-symbolic")
            icon.set_pixel_size(64)
            icon.add_css_class("dim-label")
            no_results_box.append(icon)

            no_results_label = Gtk.Label(label=_("No devices found on the network"))
            no_results_label.add_css_class("title-4")
            no_results_label.add_css_class("dim-label")
            no_results_box.append(no_results_label)

            subtitle = Gtk.Label(
                label=_(
                    "The network range may be empty or devices may be offline.\n"
                    "Try a different network range or check your connection."
                )
            )
            subtitle.add_css_class("dim-label")
            subtitle.set_justify(Gtk.Justification.CENTER)
            no_results_box.append(subtitle)

            # Add scan again button if callback is provided
            if self.scan_again_callback:
                scan_again_button = Gtk.Button(label=_("Scan Again"))
                scan_again_button.add_css_class("suggested-action")
                scan_again_button.set_size_request(160, 40)
                scan_again_button.set_margin_top(16)
                scan_again_button.set_tooltip_text(_("Start a new network scan"))
                scan_again_button.connect(
                    "clicked", lambda btn: self.scan_again_callback()
                )
                no_results_box.append(scan_again_button)

            self.results_box.append(no_results_box)
            # Show footer and separator for no results as well
            self.footer_separator.set_visible(True)
            self.footer_box.set_visible(True)
            return

        # Sort results with improved logic
        sorted_results = self.sort_results(results)

        # Create summary header
        summary_box = self.create_summary_header(sorted_results)
        self.results_box.append(summary_box)

        # Create scrolled window for results
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        # Create results container
        results_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        results_container.set_margin_start(12)
        results_container.set_margin_end(12)
        results_container.set_margin_top(8)
        results_container.set_margin_bottom(12)

        # Add results by category
        self.add_categorized_results(results_container, sorted_results)

        scrolled.set_child(results_container)
        self.results_box.append(scrolled)

    def sort_results(self, results: List[ScanResult]) -> List[ScanResult]:
        """
        Sort results with priority order:
        1. Gateways/Routers first
        2. Devices with services (ordered by service count descending)
        3. Clients without services (ordered by IP ascending)
        """
        gateways = []
        devices_with_services = []
        clients_without_services = []

        for result in results:
            # Enhance gateway identification
            enhanced_result = self.enhance_gateway_identification(result)

            if self.is_gateway(enhanced_result):
                gateways.append(enhanced_result)
            elif enhanced_result.services:
                devices_with_services.append(enhanced_result)
            else:
                clients_without_services.append(enhanced_result)

        # Sort each category
        gateways.sort(key=lambda r: self.ip_to_int(r.ip))
        devices_with_services.sort(
            key=lambda r: (-len(r.services), self.ip_to_int(r.ip))
        )
        clients_without_services.sort(key=lambda r: self.ip_to_int(r.ip))

        return gateways + devices_with_services + clients_without_services

    def enhance_gateway_identification(self, result: ScanResult) -> ScanResult:
        """Enhance gateway identification in hostnames."""
        hostname = result.hostname

        # Check if this looks like a gateway
        if self.is_gateway(result):
            # Enhance hostname for better identification
            if hostname.startswith("_gateway") or "gateway" in hostname.lower():
                if any(service.port in [80, 443] for service in result.services):
                    hostname = _("Router/Gateway") + f" ({hostname})"
                else:
                    hostname = _("Gateway") + f" ({hostname})"
            elif result.ip.endswith((".1", ".254", ".255")):
                if any(service.port in [80, 443] for service in result.services):
                    hostname = (
                        f"Router ({hostname if hostname != result.ip else result.ip})"
                    )
                else:
                    hostname = (
                        f"Gateway ({hostname if hostname != result.ip else result.ip})"
                    )

        # Create new result with enhanced hostname
        return ScanResult(
            ip=result.ip,
            hostname=hostname,
            mac=result.mac,
            vendor=result.vendor,
            services=result.services,
            response_time=result.response_time,
            is_alive=result.is_alive,
        )

    def is_gateway(self, result: ScanResult) -> bool:
        """Check if a result represents a gateway/router."""
        # Check IP patterns
        is_gateway_ip = result.ip.endswith((".1", ".254", ".255"))

        # Check hostname patterns
        hostname_lower = result.hostname.lower()
        is_gateway_hostname = any(
            term in hostname_lower
            for term in ["gateway", "router", "gw", "rt", "firewall", "fw"]
        )

        # Check if has web interface (common for routers)
        has_web_interface = any(
            service.port in [80, 443] for service in result.services
        )

        return is_gateway_ip or (is_gateway_hostname and has_web_interface)

    def ip_to_int(self, ip: str) -> int:
        """Convert IP address to integer for sorting."""
        try:
            parts = ip.split(".")
            return (
                (int(parts[0]) << 24)
                + (int(parts[1]) << 16)
                + (int(parts[2]) << 8)
                + int(parts[3])
            )
        except (ValueError, IndexError):
            return 0

    def add_categorized_results(
        self, container: Gtk.Box, results: List[ScanResult]
    ) -> None:
        """Add results organized by categories with modern UI."""
        gateways = [r for r in results if self.is_gateway(r)]
        devices_with_services = [
            r for r in results if not self.is_gateway(r) and r.services
        ]
        clients_without_services = [
            r for r in results if not self.is_gateway(r) and not r.services
        ]

        # Add Network Infrastructure section
        if gateways:
            self.add_results_section(
                container, _("🌐 Network Infrastructure"), gateways, "primary"
            )

        # Add Devices with Services section
        if devices_with_services:
            self.add_results_section(
                container, _("🖥️ Devices & Services"), devices_with_services, "secondary"
            )

        # Add Active Clients section
        if clients_without_services:
            self.add_results_section(
                container, _("📱 Active Clients"), clients_without_services, "tertiary"
            )

    def add_results_section(
        self,
        container: Gtk.Box,
        title: str,
        results: List[ScanResult],
        style_class: str,
    ) -> None:
        """Add a section of results with a title."""
        # Section header
        section_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        section_header.set_margin_top(16)
        section_header.set_margin_bottom(8)

        title_label = Gtk.Label(label=title)
        title_label.add_css_class("title-4")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_selectable(True)  # Make section titles selectable
        section_header.append(title_label)

        count_label = Gtk.Label(label=f"({len(results)})")
        count_label.add_css_class("dim-label")
        count_label.add_css_class("caption")
        section_header.append(count_label)

        container.append(section_header)

        # Devices container for pronounced visual separation (avoid listbox)
        devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        devices_box.set_margin_top(4)
        devices_box.set_margin_bottom(4)
        # Optional styling class based on section type
        devices_box.add_css_class(f"results-{style_class}-container")

        for i, result in enumerate(results):
            # Create the host expander row
            host_card = self.create_host_card(result)
            # Wrap in a styled card container for clear visual separation
            card_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            card_wrapper.add_css_class("card")
            card_wrapper.add_css_class("device-card-separated")
            # Add margins around each card
            card_wrapper.set_margin_start(8)
            card_wrapper.set_margin_end(8)
            card_wrapper.set_margin_top(4)
            card_wrapper.set_margin_bottom(4)
            card_wrapper.append(host_card)
            devices_box.append(card_wrapper)

        container.append(devices_box)

    def create_summary_header(self, results: List[ScanResult]) -> Gtk.Box:
        """Create centered summary header for scan results with softer styling."""
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header_box.set_halign(Gtk.Align.CENTER)

        # Summary info centered
        total_hosts = len(results)
        total_services = sum(len(result.services) for result in results)
        summary_label = Gtk.Label(
            label=_("Found")
            + f" {total_hosts} "
            + _("hosts with")
            + f" {total_services} "
            + _("services")
        )
        summary_label.add_css_class("title-2")
        summary_label.add_css_class("dim-label")
        summary_label.set_justify(Gtk.Justification.CENTER)
        summary_label.set_selectable(True)  # Make summary selectable
        header_box.append(summary_label)

        return header_box

    def create_host_card(self, result: ScanResult) -> Adw.ExpanderRow:
        """
        Create a modern card widget for a host result.

        Args:
            result: Scan result for the host

        Returns:
            Configured card widget with improved UI/UX
        """
        # Create expander row for the host
        expander = Adw.ExpanderRow()

        # Add right-click context menu
        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)  # Right click
        gesture.connect(
            "pressed", lambda g, n, x, y: self.show_context_menu(expander, result, x, y)
        )
        expander.add_controller(gesture)

        # Set title with IP address, hostname, and vendor on separate lines (main information)
        display_name = result.ip

        # Check if this is the local machine and add identifier to IP line
        if is_local_ip(result.ip):
            display_name += _(" (This Computer)")

        # Add hostname on new line if different from IP
        if result.hostname != result.ip:
            display_name += f"\n{result.hostname}"

        # Add vendor on new line if available and meaningful
        if result.vendor and result.vendor != "Unknown":
            display_name += f"\n{result.vendor}"

        expander.set_title(display_name)
        expander.set_title_selectable(True)  # Make title selectable

        # Create subtitle with only response time (no MAC address)
        subtitle_parts = []

        # Add response time for performance indication
        if result.response_time > 0:
            subtitle_parts.append(_("Response") + f": {result.response_time:.1f}ms")

        if subtitle_parts:
            expander.set_subtitle(" • ".join(subtitle_parts))

        # Add visual indicators and service count
        self.add_host_indicators(expander, result)

        # Create outer container for proper spacing
        outer_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer_container.set_margin_start(12)
        outer_container.set_margin_end(12)
        outer_container.set_margin_top(8)
        outer_container.set_margin_bottom(8)

        # Create expanded content container with styling
        expanded_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        expanded_container.add_css_class("device-expanded-content")

        # Add device information section for easy copying
        if result.mac or result.vendor != "Unknown" or result.ip:
            # Create wrapper box for device info styling
            device_info_wrapper = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            device_info_wrapper.add_css_class("device-info-section")

            device_info_group = Adw.PreferencesGroup()
            device_info_group.set_title(_("Device Information"))

            # IP Address row with copy button (inverted for better readability)
            ip_row = Adw.ActionRow()
            ip_row.set_title(result.ip)
            ip_row.set_subtitle(_("IP Address"))
            ip_row.set_title_selectable(True)

            ip_copy_btn = Gtk.Button()
            ip_copy_btn.set_icon_name("edit-copy-symbolic")
            ip_copy_btn.set_tooltip_text(_("Copy IP address"))
            ip_copy_btn.add_css_class("flat")
            ip_copy_btn.connect(
                "clicked", lambda btn: self.copy_to_clipboard(result.ip)
            )
            ip_row.add_suffix(ip_copy_btn)
            device_info_group.add(ip_row)

            # MAC Address row with copy button (if available) (inverted for better readability)
            if result.mac:
                mac_row = Adw.ActionRow()
                mac_row.set_title(result.mac)
                mac_row.set_subtitle(_("MAC Address"))
                mac_row.set_title_selectable(True)

                mac_copy_btn = Gtk.Button()
                mac_copy_btn.set_icon_name("edit-copy-symbolic")
                mac_copy_btn.set_tooltip_text(_("Copy MAC address"))
                mac_copy_btn.add_css_class("flat")
                mac_copy_btn.connect(
                    "clicked", lambda btn: self.copy_to_clipboard(result.mac)
                )
                mac_row.add_suffix(mac_copy_btn)
                device_info_group.add(mac_row)

            # Vendor row (if available) (inverted for better readability)
            if result.vendor and result.vendor != "Unknown":
                vendor_row = Adw.ActionRow()
                vendor_row.set_title(result.vendor)
                vendor_row.set_subtitle(_("Vendor"))
                vendor_row.set_title_selectable(True)

                vendor_copy_btn = Gtk.Button()
                vendor_copy_btn.set_icon_name("edit-copy-symbolic")
                vendor_copy_btn.set_tooltip_text(_("Copy vendor name"))
                vendor_copy_btn.add_css_class("flat")
                vendor_copy_btn.connect(
                    "clicked", lambda btn: self.copy_to_clipboard(result.vendor)
                )
                vendor_row.add_suffix(vendor_copy_btn)
                device_info_group.add(vendor_row)

            # Hostname row (if different from IP) (inverted for better readability)
            if result.hostname != result.ip:
                hostname_row = Adw.ActionRow()
                hostname_row.set_title(result.hostname)
                hostname_row.set_subtitle(_("Hostname"))
                hostname_row.set_title_selectable(True)

                hostname_copy_btn = Gtk.Button()
                hostname_copy_btn.set_icon_name("edit-copy-symbolic")
                hostname_copy_btn.set_tooltip_text(_("Copy hostname"))
                hostname_copy_btn.add_css_class("flat")
                hostname_copy_btn.connect(
                    "clicked", lambda btn: self.copy_to_clipboard(result.hostname)
                )
                hostname_row.add_suffix(hostname_copy_btn)
                device_info_group.add(hostname_row)

            device_info_wrapper.append(device_info_group)
            expanded_container.append(device_info_wrapper)

        # Create services section first (before Quick Actions)
        if result.services:
            # Create wrapper box for services styling
            services_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            services_wrapper.add_css_class("services-section")

            services_group = Adw.PreferencesGroup()
            services_group.set_title(
                _("Available Services") + f" ({len(result.services)})"
            )

            # Sort services by importance (web services first, then by port number)
            sorted_services = sorted(
                result.services,
                key=lambda s: (
                    0 if s.port in [80, 443] else 1,  # Web services first
                    1 if s.port == 22 else 2,  # SSH second
                    s.port,  # Then by port number
                ),
            )

            for service in sorted_services:
                service_row = self.create_service_row(result.ip, service)
                services_group.add(service_row)

            services_wrapper.append(services_group)
            expanded_container.append(services_wrapper)

        # Add Quick Actions section for common operations (after Services)
        quick_actions_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        quick_actions_wrapper.add_css_class("quick-actions-section")

        quick_actions_group = Adw.PreferencesGroup()
        quick_actions_group.set_title(_("Quick Actions"))

        # Ping action
        ping_row = Adw.ActionRow()
        ping_row.set_title(_("Ping Device"))
        ping_row.set_subtitle(_("Test connectivity to") + f" {result.ip}")
        ping_icon = Gtk.Image.new_from_icon_name("network-transmit-receive-symbolic")
        ping_row.add_prefix(ping_icon)

        ping_btn = Gtk.Button()
        ping_btn.set_icon_name("media-playback-start-symbolic")
        ping_btn.set_tooltip_text(_("Ping this device"))
        ping_btn.add_css_class("flat")
        ping_btn.connect("clicked", lambda btn: self.ping_device(result.ip))
        ping_row.add_suffix(ping_btn)
        quick_actions_group.add(ping_row)

        # Copy device summary action
        summary_row = Adw.ActionRow()
        summary_row.set_title(_("Copy Device Summary"))
        summary_row.set_subtitle(_("Copy all device information to clipboard"))
        summary_icon = Gtk.Image.new_from_icon_name("edit-copy-symbolic")
        summary_row.add_prefix(summary_icon)

        summary_btn = Gtk.Button()
        summary_btn.set_icon_name("edit-copy-symbolic")
        summary_btn.set_tooltip_text(_("Copy device summary"))
        summary_btn.add_css_class("flat")
        summary_btn.connect("clicked", lambda btn: self.copy_device_summary(result))
        summary_row.add_suffix(summary_btn)
        quick_actions_group.add(summary_row)

        quick_actions_wrapper.append(quick_actions_group)
        expanded_container.append(quick_actions_wrapper)

        # Add the styled container to the outer container, then to the expander
        outer_container.append(expanded_container)
        expander.add_row(outer_container)

        return expander

    def create_results_footer(self) -> Gtk.Widget:
        """Create a fixed footer for device scan actions, styled like diagnostics footer."""
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

        # Back button to return to setup view
        back_button = Gtk.Button(label=_("← Back"))
        back_button.connect(
            "clicked",
            lambda btn: self.back_callback() if self.back_callback else None,
        )
        button_container.append(back_button)

        # Export PDF button
        if self.export_pdf_callback:
            export_btn = Gtk.Button(label=_("Export PDF"))
            export_btn.set_tooltip_text(_("Export scan results to PDF file"))
            export_btn.connect("clicked", self._on_export_pdf_clicked)
            button_container.append(export_btn)

        # Scan Again button to restart scan
        if self.scan_again_callback:
            scan_again_button = Gtk.Button(label=_("Scan Again"))
            scan_again_button.add_css_class("suggested-action")
            scan_again_button.connect("clicked", lambda btn: self.scan_again_callback())
            button_container.append(scan_again_button)

        footer_box.append(button_container)
        return footer_box

    def _on_export_pdf_clicked(self, button: Gtk.Button) -> None:
        """Handle PDF export button click."""
        if self.export_pdf_callback and self.current_results:
            try:
                self.export_pdf_callback(self.current_results)
            except Exception as e:
                # Show error dialog
                dialog = Adw.MessageDialog.new(
                    button.get_root(),
                    _("Export Failed"),
                    _("Failed to export PDF") + f": {str(e)}",
                )
                dialog.add_response("ok", _("OK"))
                dialog.present()
        elif not self.current_results:
            # Show no data dialog
            dialog = Adw.MessageDialog.new(
                button.get_root(),
                _("No Data"),
                _("No scan results available to export."),
            )
            dialog.add_response("ok", _("OK"))
            dialog.present()

    def add_host_indicators(
        self, expander: Adw.ExpanderRow, result: ScanResult
    ) -> None:
        """Add visual indicators to host card."""
        # Container for indicators
        indicators_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Service count indicator
        services_count = len(result.services)
        if services_count > 0:
            services_badge = self.create_badge(
                f"{services_count}", "success" if services_count > 3 else "info"
            )
            services_badge.set_tooltip_text(
                f"{services_count} service{'s' if services_count != 1 else ''} detected"
            )
            indicators_box.append(services_badge)

        # Special indicators for important services
        service_ports = [s.port for s in result.services]

        # Web interface indicator
        if any(port in service_ports for port in [80, 443]):
            web_icon = Gtk.Image.new_from_icon_name("applications-internet-symbolic")
            web_icon.set_tooltip_text(_("Has web interface"))
            web_icon.add_css_class("success")
            indicators_box.append(web_icon)

        # SSH access indicator
        if 22 in service_ports:
            ssh_icon = Gtk.Image.new_from_icon_name("utilities-terminal-symbolic")
            ssh_icon.set_tooltip_text(_("SSH access available"))
            ssh_icon.add_css_class("accent")
            indicators_box.append(ssh_icon)

        # File sharing indicator
        if any(port in service_ports for port in [445, 139, 21]):
            share_icon = Gtk.Image.new_from_icon_name("folder-remote-symbolic")
            share_icon.set_tooltip_text(_("File sharing available"))
            share_icon.add_css_class("warning")
            indicators_box.append(share_icon)

        if indicators_box.get_first_child():
            expander.add_suffix(indicators_box)

    def create_badge(self, text: str, style: str = "info") -> Gtk.Label:
        """Create a styled badge label."""
        badge = Gtk.Label(label=text)
        badge.add_css_class("badge")
        badge.add_css_class(f"badge-{style}")
        badge.set_size_request(28, 20)
        return badge

    def create_service_row(self, ip: str, service: ServiceInfo) -> Adw.ActionRow:
        """
        Create a row widget for a service.

        Args:
            ip: Host IP address
            service: Service information

        Returns:
            Configured service row
        """
        row = Adw.ActionRow()
        # Invert title and subtitle for better readability
        row.set_title(
            _("Port") + f" {service.port}/{service.protocol} - {service.description}"
        )
        row.set_title_selectable(True)  # Make port info selectable
        row.set_subtitle(service.name)

        # Set enhanced tooltip with access information
        tooltip_parts = [
            service.name,
            _("Port") + f": {service.port}/{service.protocol}",
            _("Description") + f": {service.description}",
        ]

        if service.access_method:
            if service.access_method in ["http", "https"]:
                tooltip_parts.append(
                    _("Access") + f": {service.access_method}://{ip}:{service.port}"
                )
            elif service.access_method == "ssh":
                tooltip_parts.append(
                    _("SSH Terminal") + f": ssh <username>@{ip} -p {service.port}"
                )
                tooltip_parts.append(
                    _("SFTP Files") + f": sftp://<username>@{ip}:{service.port}"
                )
            elif service.access_method == "smb":
                tooltip_parts.append(_("Access") + f": smb://{ip}")
            elif service.access_method == "ftp":
                tooltip_parts.append(_("Access") + f": ftp://{ip}:{service.port}")

        tooltip_text = "\n".join(tooltip_parts)
        row.set_tooltip_text(tooltip_text)

        # Add service icon based on type
        icon_name = self.get_service_icon(service)
        if icon_name:
            icon = Gtk.Image.new_from_icon_name(icon_name)
            row.add_prefix(icon)

        # Create action buttons container
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        # Add copy button for the service URL/address
        copy_button = Gtk.Button()
        copy_button.set_icon_name("edit-copy-symbolic")
        copy_button.set_tooltip_text(_("Copy service address"))
        copy_button.add_css_class("flat")
        copy_button.connect(
            "clicked", lambda btn: self.copy_service_address(ip, service)
        )
        actions_box.append(copy_button)

        # Add specialized buttons based on service type
        if service.access_method in ["http", "https"]:
            # Web interface - add both open browser and copy URL buttons
            browser_button = Gtk.Button()
            browser_button.set_icon_name("applications-internet-symbolic")
            browser_button.set_tooltip_text(
                _("Open in browser: ")
                + f"{service.access_method}://{ip}:{service.port}"
            )
            browser_button.add_css_class("flat")
            browser_button.connect(
                "clicked", lambda btn: self.open_service_callback(ip, service)
            )
            actions_box.append(browser_button)

        elif service.access_method == "ssh":
            # SSH - add both terminal and file manager options
            terminal_button = Gtk.Button()
            terminal_button.set_icon_name("utilities-terminal-symbolic")
            terminal_button.set_tooltip_text(_("Open SSH connection in terminal"))
            terminal_button.add_css_class("flat")
            terminal_button.connect(
                "clicked", lambda btn: self.show_ssh_dialog(ip, service.port)
            )
            actions_box.append(terminal_button)

            # SFTP file manager button
            sftp_button = Gtk.Button()
            sftp_button.set_icon_name("folder-remote-symbolic")
            sftp_button.set_tooltip_text(_("Open SFTP in file manager"))
            sftp_button.add_css_class("flat")
            sftp_button.connect(
                "clicked", lambda btn: self.open_sftp_files(ip, service.port)
            )
            actions_box.append(sftp_button)

        elif service.access_method == "smb":
            # SMB/Samba - add file manager button
            files_button = Gtk.Button()
            files_button.set_icon_name("folder-remote-symbolic")
            files_button.set_tooltip_text(_("Open in file manager: ") + f"smb://{ip}")
            files_button.add_css_class("flat")
            files_button.connect(
                "clicked", lambda btn: self.open_service_callback(ip, service)
            )
            actions_box.append(files_button)

        elif service.access_method == "ftp":
            # FTP - add file manager button
            ftp_button = Gtk.Button()
            ftp_button.set_icon_name("folder-download-symbolic")
            ftp_button.set_tooltip_text(_("Open FTP: ") + f"ftp://{ip}:{service.port}")
            ftp_button.add_css_class("flat")
            ftp_button.connect(
                "clicked", lambda btn: self.open_service_callback(ip, service)
            )
            actions_box.append(ftp_button)

        # Add open button if service can be opened and we haven't added specific button
        elif service.access_method:
            open_button = Gtk.Button()
            open_button.set_icon_name("external-link-symbolic")
            open_button.set_tooltip_text(_("Open") + f" {service.name}")
            open_button.add_css_class("flat")
            open_button.connect(
                "clicked", lambda btn: self.open_service_callback(ip, service)
            )
            actions_box.append(open_button)

        row.add_suffix(actions_box)

        return row

    def get_service_icon(self, service: ServiceInfo) -> Optional[str]:
        """
        Get appropriate icon for a service.

        Args:
            service: Service information

        Returns:
            Icon name or None
        """
        icon_map = {
            "http": "applications-internet-symbolic",
            "https": "network-wireless-encrypted-symbolic",
            "ssh": "utilities-terminal-symbolic",
            "smb": "folder-remote-symbolic",
            "ftp": "folder-download-symbolic",
            "rdp": "preferences-desktop-remote-desktop-symbolic",
            "vnc": "preferences-desktop-remote-desktop-symbolic",
        }

        return icon_map.get(service.access_method, "network-server-symbolic")

    def copy_service_address(self, ip: str, service: ServiceInfo) -> None:
        """
        Copy service address to clipboard with enhanced formats.

        Args:
            ip: Host IP address
            service: Service information
        """
        addresses = []

        if service.access_method in ["http", "https"]:
            # For standard ports, use the clean URL format
            if (service.access_method == "http" and service.port == 80) or (
                service.access_method == "https" and service.port == 443
            ):
                addresses.append(f"{service.access_method}://{ip}")
            else:
                # For non-standard ports, include the port number
                addresses.append(f"{service.access_method}://{ip}:{service.port}")
        elif service.access_method == "ssh":
            # SSH Terminal options
            addresses.append(f"ssh <username>@{ip} -p {service.port}")
            if service.port == 22:
                addresses.append(f"ssh <username>@{ip}")

            # SFTP File Manager options
            if service.port == 22:
                addresses.append(f"sftp://<username>@{ip}")
            else:
                addresses.append(f"sftp://<username>@{ip}:{service.port}")

            addresses.append("# Common usernames: root, admin, pi, user")
            addresses.append("# SSH for terminal, SFTP for file manager")
        elif service.access_method == "smb":
            addresses.append(f"smb://{ip}")
        elif service.access_method == "ftp":
            addresses.append(f"ftp://{ip}:{service.port}")
            addresses.append(f"ftp user@{ip}:{service.port}")
        else:
            addresses.append(f"{ip}:{service.port}")
            addresses.append(f"telnet {ip} {service.port}")

        # Join multiple formats with newlines for easy access
        address = "\n".join(addresses) if len(addresses) > 1 else addresses[0]

        # Copy to clipboard
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(address)

    def copy_to_clipboard(self, text: str) -> None:
        """
        Copy text to clipboard with user feedback.

        Args:
            text: Text to copy to clipboard
        """
        try:
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set(text)
            # TODO: Add toast notification for copy feedback
        except Exception as e:
            print(f"Failed to copy to clipboard: {e}")

    def show_ssh_dialog(self, ip: str, port: int = 22) -> None:
        """
        Show SSH connection dialog to get username.

        Args:
            ip: Target IP address
            port: SSH port (default 22)
        """
        # Create dialog
        dialog = Adw.MessageDialog.new(
            None,
            _("SSH Connection"),
            _("Connect to") + f" {ip}:{port}",
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

        # Info label
        info_label = Gtk.Label(
            label=_("This will open SSH connection in your terminal")
        )
        info_label.add_css_class("dim-label")
        info_label.add_css_class("caption")
        content_box.append(info_label)

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
                if username:
                    self.open_ssh_terminal_with_user(ip, port, username)
                else:
                    self.open_ssh_terminal_with_user(ip, port, "root")
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
            # Try different terminal emulators
            terminals = [
                ["ptyxis", "--", "ssh", f"{username}@{ip}", "-p", str(port)],
                ["tilix", "-e", "ssh", f"{username}@{ip}", "-p", str(port)],
                ["gnome-terminal", "--", "ssh", f"{username}@{ip}", "-p", str(port)],
                ["konsole", "-e", "ssh", f"{username}@{ip}", "-p", str(port)],
                ["xfce4-terminal", "-e", f"ssh {username}@{ip} -p {port}"],
                ["xterm", "-e", f"ssh {username}@{ip} -p {port}"],
            ]

            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(
                        terminal_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    break
                except FileNotFoundError:
                    continue
            else:
                # Fallback: copy SSH command to clipboard
                ssh_command = f"ssh {username}@{ip} -p {port}"
                self.copy_to_clipboard(ssh_command)
        except Exception as e:
            print(f"Failed to open SSH terminal: {e}")
            # Fallback: copy SSH command to clipboard
            ssh_command = f"ssh {username}@{ip} -p {port}"
            self.copy_to_clipboard(ssh_command)

    def open_ssh_terminal(self, ip: str, port: int = 22) -> None:
        """
        Open SSH connection in terminal.

        Args:
            ip: Target IP address
            port: SSH port (default 22)
        """
        try:
            # Try different terminal emulators
            terminals = [
                ["ptyxis", "--", "ssh", f"user@{ip}", "-p", str(port)],
                ["tilix", "-e", "ssh", f"user@{ip}", "-p", str(port)],
                ["gnome-terminal", "--", "ssh", f"user@{ip}", "-p", str(port)],
                ["konsole", "-e", "ssh", f"user@{ip}", "-p", str(port)],
                ["xfce4-terminal", "-e", f"ssh user@{ip} -p {port}"],
                ["xterm", "-e", f"ssh user@{ip} -p {port}"],
            ]

            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(
                        terminal_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    break
                except FileNotFoundError:
                    continue
            else:
                # Fallback: copy SSH command to clipboard
                ssh_command = f"ssh user@{ip} -p {port}"
                self.copy_to_clipboard(ssh_command)
        except Exception as e:
            print(f"Failed to open SSH terminal: {e}")
            # Fallback: copy SSH command to clipboard
            ssh_command = f"ssh user@{ip} -p {port}"
            self.copy_to_clipboard(ssh_command)

    def ping_device(self, ip: str) -> None:
        """
        Show built-in ping dialog with real-time results.

        Args:
            ip: Target IP address
        """
        # Get the main window as parent
        parent_window = self.get_root()

        # Create and show ping dialog
        ping_dialog = PingDialog(parent_window, ip)
        ping_dialog.present()

        # Auto-start ping
        ping_dialog.start_ping()

    def copy_device_summary(self, result: ScanResult) -> None:
        """
        Copy comprehensive device summary to clipboard.

        Args:
            result: Scan result containing device information
        """
        summary_lines = []

        # Header
        summary_lines.append(_("=== Device Summary ==="))
        summary_lines.append(f"{_('Hostname')}: {result.hostname}")
        summary_lines.append(f"{_('IP Address')}: {result.ip}")

        if result.mac:
            summary_lines.append(f"{_('MAC Address')}: {result.mac}")

        if result.vendor and result.vendor != "Unknown":
            summary_lines.append(f"{_('Vendor')}: {result.vendor}")

        if result.response_time > 0:
            summary_lines.append(f"{_('Response Time')}: {result.response_time:.1f}ms")

        # Services section
        if result.services:
            summary_lines.append(f"\n=== {_('Services')} ({len(result.services)}) ===")
            for service in sorted(result.services, key=lambda s: s.port):
                service_line = (
                    f"{service.name} - Port {service.port}/{service.protocol}"
                )
                if service.access_method:
                    if service.access_method in ["http", "https"]:
                        service_line += (
                            f" - {service.access_method}://{result.ip}:{service.port}"
                        )
                    elif service.access_method == "ssh":
                        service_line += f" - ssh <username>@{result.ip}:{service.port}"
                    elif service.access_method == "smb":
                        service_line += f" - smb://{result.ip}"
                    elif service.access_method == "ftp":
                        service_line += f" - ftp://{result.ip}:{service.port}"
                summary_lines.append(service_line)
        else:
            summary_lines.append(_("=== Services ==="))
            summary_lines.append(_("No services detected"))

        # Quick commands section
        summary_lines.append(_("=== Quick Commands ==="))
        summary_lines.append(f"ping {result.ip}")

        if any(s.access_method == "ssh" for s in result.services):
            ssh_service = next(s for s in result.services if s.access_method == "ssh")
            summary_lines.append(f"ssh <username>@{result.ip} -p {ssh_service.port}")
            summary_lines.append(
                _("# Replace <username> with: root, admin, pi, or your username")
            )

        if any(s.access_method in ["http", "https"] for s in result.services):
            web_service = next(
                s for s in result.services if s.access_method in ["http", "https"]
            )
            summary_lines.append(
                f"{web_service.access_method}://{result.ip}:{web_service.port}"
            )

        summary_text = "\n".join(summary_lines)
        self.copy_to_clipboard(summary_text)

    def show_context_menu(
        self, widget: Gtk.Widget, result: ScanResult, x: float, y: float
    ) -> None:
        """
        Show context menu for device actions.

        Args:
            widget: Widget that triggered the menu
            result: Scan result for the device
            x, y: Click coordinates
        """
        menu = Gio.Menu()

        # Copy actions
        copy_section = Gio.Menu()
        copy_section.append(_("Copy IP Address"), f"app.copy-ip::{result.ip}")
        if result.mac:
            copy_section.append(_("Copy MAC Address"), f"app.copy-mac::{result.mac}")
        if result.hostname != result.ip:
            copy_section.append(
                _("Copy Hostname"), f"app.copy-hostname::{result.hostname}"
            )
        copy_section.append(_("Copy Device Summary"), f"app.copy-summary::{result.ip}")
        menu.append_section(_("Copy"), copy_section)

        # Quick actions
        actions_section = Gio.Menu()
        actions_section.append(_("Ping Device"), f"app.ping::{result.ip}")

        # Service actions
        if result.services:
            for service in result.services:
                if service.access_method in ["http", "https"]:
                    actions_section.append(
                        f"Open {service.name}",
                        f"app.open-service::{result.ip}::{service.port}",
                    )
                elif service.access_method == "ssh":
                    actions_section.append(
                        _("Open SSH Terminal"), f"app.ssh::{result.ip}::{service.port}"
                    )
                elif service.access_method == "smb":
                    actions_section.append(
                        _("Open File Share"),
                        f"app.open-service::{result.ip}::{service.port}",
                    )

        menu.append_section("Actions", actions_section)

        # Create and show popover
        popover = Gtk.PopoverMenu()
        popover.set_menu_model(menu)
        popover.set_parent(widget)
        popover.set_pointing_to(Gdk.Rectangle(x, y, 1, 1))
        popover.popup()

    def open_sftp_files(self, ip: str, port: int = 22) -> None:
        """
        Open SFTP connection in file manager.

        Args:
            ip: Target IP address
            port: SSH/SFTP port (default 22)
        """
        # Create dialog for username
        dialog = Adw.MessageDialog.new(
            None, _("SFTP Connection"), _("Connect to SFTP at") + f" {ip}:{port}"
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

        # Info label
        info_label = Gtk.Label(
            label=_("This will open SFTP connection in your file manager")
        )
        info_label.add_css_class("dim-label")
        info_label.add_css_class("caption")
        content_box.append(info_label)

        # Set the content
        dialog.set_extra_child(content_box)

        # Add buttons
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("connect", _("Open SFTP"))
        dialog.set_response_appearance("connect", Adw.ResponseAppearance.SUGGESTED)

        # Handle response
        def on_response(dialog, response):
            if response == "connect":
                username = username_entry.get_text().strip()
                if username:
                    self.open_sftp_with_user(ip, port, username)
                else:
                    self.open_sftp_with_user(ip, port, "root")
            dialog.destroy()

        dialog.connect("response", on_response)

        # Focus the entry and select all text
        username_entry.grab_focus()
        username_entry.select_region(0, -1)

        dialog.present()

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
            print(f"Failed to open SFTP: {e}")
            # Fallback: copy SFTP URL to clipboard
            if port == 22:
                sftp_url = f"sftp://{username}@{ip}"
            else:
                sftp_url = f"sftp://{username}@{ip}:{port}"
            self.copy_to_clipboard(sftp_url)


class PingDialog(Adw.Window):
    """Built-in ping dialog with real-time results."""

    def __init__(self, parent_window, target_ip: str):
        """Initialize the ping dialog."""
        super().__init__()
        self.set_title(_("Ping") + f" - {target_ip}")
        self.set_modal(True)
        self.set_transient_for(parent_window)
        self.set_default_size(700, 400)

        self.target_ip = target_ip
        self.ping_process = None
        self.ping_thread = None
        self.is_running = False

        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)

        # Header with target info
        header_group = Adw.PreferencesGroup()
        header_group.set_title(_("Pinging") + f" {self.target_ip}")
        header_group.set_description(_("Real-time ping results and statistics"))

        # Status row
        self.status_row = Adw.ActionRow()
        self.status_row.set_title(_("Status"))
        self.status_row.set_subtitle(_("Preparing to ping..."))
        self.status_icon = Gtk.Image.new_from_icon_name(
            "network-wireless-signal-good-symbolic"
        )
        self.status_row.add_prefix(self.status_icon)
        header_group.add(self.status_row)

        main_box.append(header_group)

        # Scrollable text view for ping output
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(200)

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_monospace(True)
        self.text_view.set_margin_start(12)
        self.text_view.set_margin_end(12)
        self.text_view.set_margin_top(12)
        self.text_view.set_margin_bottom(12)

        self.text_buffer = self.text_view.get_buffer()
        scrolled.set_child(self.text_view)

        # Wrap the scrolled window in a frame for better appearance
        frame = Gtk.Frame()
        frame.set_child(scrolled)
        frame.add_css_class("card")

        # Add frame directly to the main box instead of using PreferencesGroup
        results_label = Gtk.Label()
        results_label.set_text(_("Ping Results"))
        results_label.set_halign(Gtk.Align.START)
        results_label.add_css_class("title-4")
        results_label.set_margin_bottom(12)

        main_box.append(results_label)
        main_box.append(frame)

        # Button row
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.END)

        # Copy button
        self.copy_btn = Gtk.Button.new_with_label(_("Copy Results"))
        self.copy_btn.set_icon_name("edit-copy-symbolic")
        self.copy_btn.connect("clicked", self.on_copy_clicked)
        button_box.append(self.copy_btn)

        # Cancel/Stop button
        self.cancel_btn = Gtk.Button.new_with_label(_("Start Ping"))
        self.cancel_btn.set_icon_name("media-playback-start-symbolic")
        self.cancel_btn.add_css_class("suggested-action")
        self.cancel_btn.connect("clicked", self.on_cancel_clicked)
        button_box.append(self.cancel_btn)

        # Close button
        close_btn = Gtk.Button.new_with_label(_("Close"))
        close_btn.connect("clicked", lambda x: self.close())
        button_box.append(close_btn)

        main_box.append(button_box)

        self.set_content(main_box)

    def start_ping(self):
        """Start the ping process."""
        if self.is_running:
            return

        self.is_running = True

        self.cancel_btn.set_label(_("Stop Ping"))
        self.cancel_btn.set_icon_name("media-playback-stop-symbolic")
        self.cancel_btn.remove_css_class("suggested-action")
        self.cancel_btn.add_css_class("destructive-action")

        self.status_row.set_subtitle(_("Pinging..."))
        self.status_icon.set_from_icon_name("network-transmit-receive-symbolic")

        # Clear previous results
        self.text_buffer.set_text("")

        # Start ping in a separate thread
        self.ping_thread = threading.Thread(target=self._ping_worker, daemon=True)
        self.ping_thread.start()

    def stop_ping(self):
        """Stop the ping process."""
        self.is_running = False

        if self.ping_process:
            try:
                self.ping_process.terminate()
            except:
                pass

        self.cancel_btn.set_label(_("Start Ping"))
        self.cancel_btn.set_icon_name("media-playback-start-symbolic")
        self.cancel_btn.remove_css_class("destructive-action")
        self.cancel_btn.add_css_class("suggested-action")

        GLib.idle_add(self._update_status_finished)

    def _update_status_finished(self):
        """Update status when ping is finished."""
        self.status_row.set_subtitle(_("Ping completed"))
        self.status_icon.set_from_icon_name("object-select-symbolic")

    def _ping_worker(self):
        """Worker thread for ping process."""
        try:
            cmd = ["ping", "-c", "10", self.target_ip]

            self.ping_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
            )

            # Process output line by line
            for line in iter(self.ping_process.stdout.readline, ""):
                if not self.is_running:
                    break

                line = line.strip()
                if line:
                    GLib.idle_add(self._append_output, line)

        except Exception as e:
            GLib.idle_add(self._append_output, f"Error: {str(e)}")
        finally:
            if self.is_running:
                GLib.idle_add(self.stop_ping)

    def _append_output(self, text: str):
        """Append text to output (called from main thread)."""
        end_iter = self.text_buffer.get_end_iter()
        self.text_buffer.insert(end_iter, text + "\n")

        # Auto-scroll to bottom
        mark = self.text_buffer.get_insert()
        self.text_view.scroll_mark_onscreen(mark)

    def on_cancel_clicked(self, button):
        """Handle cancel/start button click."""
        if self.is_running:
            self.stop_ping()
        else:
            self.start_ping()

    def on_copy_clicked(self, button):
        """Copy ping results to clipboard."""
        start_iter = self.text_buffer.get_start_iter()
        end_iter = self.text_buffer.get_end_iter()
        text = self.text_buffer.get_text(start_iter, end_iter, False)

        if text.strip():
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set(text)

            # Brief visual feedback
            original_label = button.get_label()
            button.set_label(_("Copied!"))
            if original_label is not None:
                GLib.timeout_add(
                    1000, lambda: button.set_label(original_label) and False
                )
            else:
                GLib.timeout_add(1000, lambda: button.set_label(_("Copy")) and False)
