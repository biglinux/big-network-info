#!/usr/bin/env python3
"""
Channel Usage Table Implementation
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib
from .translation import _


class ChannelUsageTable(Gtk.Box):
    """Table showing channel usage with network details and copy functionality"""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Create header with copy button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_box.set_margin_top(6)
        header_box.set_margin_bottom(6)
        header_box.set_margin_start(12)
        header_box.set_margin_end(12)

        # Title label
        title_label = Gtk.Label(label=_("Channel Usage Details"))
        title_label.add_css_class("heading")
        title_label.set_halign(Gtk.Align.START)
        header_box.append(title_label)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_box.append(spacer)

        # Copy button
        self.copy_button = Gtk.Button(label=_("Copy WiFi Data"))
        self.copy_button.add_css_class("suggested-action")
        self.copy_button.connect("clicked", self._on_copy_clicked)
        header_box.append(self.copy_button)

        self.append(header_box)

        # Create scrolled window for the table
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(300)
        scrolled.set_vexpand(True)

        # Create the list store and tree view
        # Columns: Channel, Frequency, Network Name, BSSID, Signal Strength, Security
        self.store = Gtk.ListStore(int, str, str, str, str, str)
        self.tree_view = Gtk.TreeView(model=self.store)

        # Set up columns
        self._setup_columns()

        # Apply dark theme styling
        self.tree_view.get_style_context().add_class("view")

        scrolled.set_child(self.tree_view)
        self.append(scrolled)

        self.data = {}
        self.signal_data = {}

    def _setup_columns(self):
        """Set up the table columns"""
        columns = [
            (_("Channel"), 0, 80),
            (_("Frequency"), 1, 100),
            (_("Network Name"), 2, 200),
            (_("BSSID"), 3, 150),
            (_("Signal"), 4, 80),
            (_("Security"), 5, 100),
        ]

        for title, col_id, width in columns:
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=col_id)
            column.set_resizable(True)
            column.set_min_width(width)
            column.set_sort_column_id(col_id)

            # Center align numeric columns
            if col_id in [0, 1, 4]:
                renderer.set_property("xalign", 0.5)
                column.set_alignment(0.5)

            self.tree_view.append_column(column)

        # Enable sorting
        self.store.set_sort_column_id(0, Gtk.SortType.ASCENDING)

    def _channel_to_frequency(self, channel):
        """Convert WiFi channel to frequency in MHz"""
        try:
            channel = int(channel)
            # 2.4 GHz channels
            if 1 <= channel <= 14:
                if channel == 14:
                    return "2484 MHz"
                else:
                    return f"{2412 + (channel - 1) * 5} MHz"

            # 5 GHz channels (simplified)
            elif 36 <= channel <= 165:
                return f"{5000 + channel * 5} MHz"

            return _("Unknown")
        except (ValueError, TypeError):
            return _("Unknown")

    def _get_security_info(self, network_data):
        """Extract security information from network data"""
        if hasattr(network_data, "security") and network_data.security:
            return network_data.security
        elif hasattr(network_data, "encryption") and network_data.encryption:
            return network_data.encryption
        else:
            return _("Open")

    def update_data(self, data, signal_data=None):
        """Update table data with channel and network information"""
        self.data = data  # This is channel_usage: Dict[int, List[str]]
        self.signal_data = (
            signal_data or {}
        )  # This is history_data: Dict[str, List[WiFiNetwork]]

        # Clear existing data
        self.store.clear()

        if not self.data:
            return

        # data is channel_usage: {channel: [network_names]}
        # signal_data is history_data: {network_key: [WiFiNetwork]}

        # Sort channels numerically
        sorted_channels = sorted(self.data.keys())

        # Add data to the store
        added_bssids = set()  # Track added BSSIDs to avoid true duplicates

        for channel in sorted_channels:
            frequency = self._channel_to_frequency(str(channel))

            # Find all networks on this channel directly from signal data
            networks_on_channel = []

            for key, history in self.signal_data.items():
                if history:
                    latest_network = history[-1]
                    # Check if this network is on the current channel
                    if latest_network.channel == channel:
                        # Only add if we haven't seen this BSSID before
                        if latest_network.bssid not in added_bssids:
                            networks_on_channel.append(latest_network)
                            added_bssids.add(latest_network.bssid)

            # Sort networks by signal strength (strongest first)
            networks_on_channel.sort(key=lambda x: x.signal_level, reverse=True)

            # Add each unique network to the store
            for network_data in networks_on_channel:
                # Prepare display data
                display_name = (
                    network_data.ssid
                    if network_data.ssid and network_data.ssid != "Hidden Network"
                    else _("Hidden Network")
                )
                bssid = network_data.bssid
                signal_strength = f"{network_data.signal_level}%"
                security = self._get_security_info(network_data)

                # Add row to store
                self.store.append([
                    channel,
                    frequency,
                    display_name,
                    bssid,
                    signal_strength,
                    security,
                ])

    def _on_copy_clicked(self, button):
        """Copy all table data to clipboard with proper column alignment"""
        if not self.store:
            return

        # Collect all data first to calculate optimal column widths
        all_rows = []

        # Add header row
        headers = [
            _("Channel"),
            _("Frequency"),
            _("Network Name"),
            _("BSSID"),
            _("Signal"),
            _("Security"),
        ]
        all_rows.append(headers)

        # Collect data rows
        iter_row = self.store.get_iter_first()
        while iter_row is not None:
            row_data = []
            for col in range(6):  # 6 columns
                value = self.store.get_value(iter_row, col)
                row_data.append(str(value))
            all_rows.append(row_data)
            iter_row = self.store.iter_next(iter_row)

        if len(all_rows) <= 1:  # Only headers, no data
            return

        # Calculate optimal column widths
        col_widths = [0] * 6
        for row in all_rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # Add some padding to each column
        col_widths = [width + 3 for width in col_widths]

        # Format the table with proper alignment
        lines = []

        for row_idx, row in enumerate(all_rows):
            formatted_cells = []
            for i, cell in enumerate(row):
                cell_str = str(cell)
                # Right-align numeric columns (Channel, Signal), left-align others
                if i in [0, 4]:  # Channel and Signal columns
                    if i == 4:  # Signal column - add extra space after
                        formatted_cell = cell_str.rjust(col_widths[i] - 2) + "  "
                    else:  # Channel column
                        formatted_cell = cell_str.rjust(col_widths[i])
                else:
                    formatted_cell = cell_str.ljust(col_widths[i])
                formatted_cells.append(formatted_cell)

            # Join cells and ensure clean output
            line = "".join(formatted_cells).rstrip()
            lines.append(line)

            # Add separator line after header
            if row_idx == 0:
                separator_parts = []
                for i, width in enumerate(col_widths):
                    separator_parts.append("-" * width)
                separator_line = "".join(separator_parts).rstrip()
                lines.append(separator_line)

        # Join all lines
        table_text = "\n".join(lines)

        # Copy to clipboard
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(table_text)

        # Show temporary feedback
        original_label = button.get_label()
        button.set_label(_("Copied!"))
        button.set_sensitive(False)

        # Reset button after 2 seconds
        def reset_button():
            button.set_label(original_label)
            button.set_sensitive(True)
            return False

        GLib.timeout_add_seconds(2, reset_button)
