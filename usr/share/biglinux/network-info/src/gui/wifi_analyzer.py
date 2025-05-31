#!/usr/bin/env python3
"""
WiFi Analyzer GUI with Cairo-based visualizations
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib
import cairo
import math
import colorsys
from datetime import datetime, timedelta

from ..core.wifi_scanner import WiFiScanner
from .channel_table import ChannelUsageTable
from .translation import _


class WiFiChart(Gtk.DrawingArea):
    """Base class for WiFi visualization charts using Cairo"""

    def __init__(self):
        super().__init__()
        # Remove fixed size and allow expansion
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_draw_func(self._on_draw)
        self.colors = {}
        self.data = {}

    def _on_draw(self, area, cr, width, height):
        """Override this method in subclasses"""
        pass

    def _generate_color(self, ssid: str) -> tuple:
        """Generate a unique color for each SSID with better readability"""
        if ssid not in self.colors:
            # Predefined high-contrast colors for better readability
            predefined_colors = [
                (0.2, 0.8, 1.0),  # Bright cyan
                (1.0, 0.3, 0.3),  # Bright red
                (0.3, 1.0, 0.3),  # Bright green
                (1.0, 0.8, 0.2),  # Bright orange
                (0.8, 0.3, 1.0),  # Bright purple
                (1.0, 0.6, 0.8),  # Bright pink
                (0.4, 1.0, 0.8),  # Bright mint
                (1.0, 1.0, 0.3),  # Bright yellow
                (0.6, 0.8, 1.0),  # Light blue
                (1.0, 0.5, 0.1),  # Orange red
                (0.1, 0.9, 0.6),  # Teal
                (0.9, 0.2, 0.8),  # Magenta
                (0.7, 0.9, 0.2),  # Lime green
                (0.2, 0.6, 1.0),  # Blue
                (1.0, 0.4, 0.6),  # Rose
            ]

            # Use predefined colors first, then generate if needed
            num_existing = len(self.colors)
            if num_existing < len(predefined_colors):
                rgb = predefined_colors[num_existing]
            else:
                # Generate additional colors with high contrast
                hash_val = hash(ssid)
                hue = (hash_val % 360) / 360.0
                saturation = 0.8 + (hash_val % 20) / 100.0  # 0.8-1.0 for vibrant colors
                value = 0.9 + (hash_val % 10) / 100.0  # 0.9-1.0 for bright colors
                rgb = colorsys.hsv_to_rgb(hue, saturation, value)

            self.colors[ssid] = rgb

        return self.colors[ssid]

    def update_data(self, data):
        """Update chart data and trigger redraw"""
        self.data = data
        self.queue_draw()


class SignalStrengthChart(WiFiChart):
    """Chart showing signal strength over time for WiFi networks"""

    def __init__(self):
        super().__init__()
        # Set minimum size but allow expansion with increased height
        self.set_size_request(400, 500)
        self.history_minutes = 2
        self.max_networks = 50  # Increased to show up to 50 networks

        # Mouse hover functionality
        self.hover_network = None
        self.hover_x = 0
        self.hover_y = 0

        # Set up mouse motion events
        self.set_can_focus(True)
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect("motion", self._on_mouse_motion)
        motion_controller.connect("leave", self._on_mouse_leave)
        self.add_controller(motion_controller)

    def _on_draw(self, area, cr, width, height):
        """Draw the signal strength over time chart"""
        cr.set_source_rgb(0.15, 0.15, 0.15)  # Dark background
        cr.paint()

        if not self.data:
            self._draw_no_data_message(cr, width, height)
            return

        # Define margins - adjusted for right-side signal labels and left-side legend
        margin_left = 250  # Keep for left-side legend
        margin_right = 80  # Increased for right-side signal strength labels
        margin_top = 30
        margin_bottom = 60

        chart_width = width - margin_left - margin_right
        chart_height = height - margin_top - margin_bottom

        if chart_width <= 0 or chart_height <= 0:
            return

        # Draw chart background with better contrast
        cr.set_source_rgb(
            0.1, 0.1, 0.1
        )  # Darker chart background for better line visibility
        cr.rectangle(margin_left, margin_top, chart_width, chart_height)
        cr.fill()

        # Draw border
        cr.set_source_rgb(0.5, 0.5, 0.5)  # Light gray border for dark theme
        cr.set_line_width(1)
        cr.rectangle(margin_left, margin_top, chart_width, chart_height)
        cr.stroke()

        # Draw grid and axes
        self._draw_grid(cr, margin_left, margin_top, chart_width, chart_height)
        self._draw_axes(
            cr, margin_left, margin_top, chart_width, chart_height, width, height
        )

        # Draw data lines
        self._draw_signal_lines(cr, margin_left, margin_top, chart_width, chart_height)

        # Draw legend
        self._draw_legend(cr, width, height, margin_top)

        # Draw tooltip if hovering over a network
        self._draw_tooltip(cr, width, height)

    def _draw_no_data_message(self, cr, width, height):
        """Draw a message when no data is available"""
        cr.set_source_rgb(0.7, 0.7, 0.7)  # Light gray for dark theme
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(16)

        text = _("Scanning for WiFi networks...")
        text_extents = cr.text_extents(text)
        x = (width - text_extents.width) / 2
        y = (height + text_extents.height) / 2

        cr.move_to(x, y)
        cr.show_text(text)

    def _draw_grid(self, cr, x, y, width, height):
        """Draw grid lines"""
        cr.set_source_rgb(0.4, 0.4, 0.4)  # Dark theme grid
        cr.set_line_width(0.5)

        # Horizontal grid lines (signal levels)
        for i in range(5):
            grid_y = y + (height / 4) * i
            cr.move_to(x, grid_y)
            cr.line_to(x + width, grid_y)
            cr.stroke()

        # Vertical grid lines (time)
        for i in range(6):
            grid_x = x + (width / 5) * i
            cr.move_to(grid_x, y)
            cr.line_to(grid_x, y + height)
            cr.stroke()

    def _draw_axes(self, cr, x, y, width, height, total_width, total_height):
        """Draw axes labels"""
        cr.set_source_rgb(0.8, 0.8, 0.8)  # Light text for dark theme
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)

        # Y-axis labels (signal strength) - moved to right side
        # Labels correspond to grid lines: 100%, 75%, 50%, 25%, 0%
        signal_levels = ["100%", "75%", "50%", "25%", "0%"]
        for i, label in enumerate(signal_levels):
            label_y = y + (height / 4) * i + 4
            # Position labels on the right side of the chart
            cr.move_to(x + width + 10, label_y)
            cr.show_text(label)

        # X-axis labels (time)
        now = datetime.now()
        for i in range(6):
            time_offset = (self.history_minutes / 5) * (5 - i)
            time_point = now - timedelta(minutes=time_offset)
            time_str = time_point.strftime("%H:%M")

            text_extents = cr.text_extents(time_str)
            label_x = x + (width / 5) * i - text_extents.width / 2
            label_y = y + height + 15

            cr.move_to(label_x, label_y)
            cr.show_text(time_str)

        # Axis titles
        cr.set_font_size(12)

        # Y-axis title - moved to right side
        cr.save()
        cr.translate(total_width - 15, y + height / 2)
        cr.rotate(-math.pi / 2)
        text_extents = cr.text_extents(_("Signal Strength (%)"))
        cr.move_to(-text_extents.width / 2, 0)
        cr.show_text(_("Signal Strength (%)"))
        cr.restore()

        # X-axis title
        text_extents = cr.text_extents(_("Time"))
        cr.move_to(x + width / 2 - text_extents.width / 2, total_height - 10)
        cr.show_text(_("Time"))

    def _draw_signal_lines(self, cr, x, y, width, height):
        """Draw signal strength lines for each network"""
        if not self.data:
            return

        now = datetime.now()
        start_time = now - timedelta(minutes=self.history_minutes)

        # Sort networks by current signal strength (0-100 scale, higher is better)
        sorted_networks = sorted(
            self.data.items(),
            key=lambda item: item[1][-1].signal_level if item[1] else 0,
            reverse=True,
        )

        # Limit number of networks for readability
        networks_to_draw = sorted_networks[: self.max_networks]

        # Improved line width for better visibility
        cr.set_line_width(3)  # Increased from 2 to 3 for better visibility

        for network_key, history in networks_to_draw:
            if not history:
                continue

            # Get display name for the network
            network = history[-1]  # Get latest network data
            if network.ssid and network.ssid != "Hidden Network":
                display_name = network.ssid
            else:
                display_name = f"Hidden-{network.bssid[-8:]}"

            # Set color for this network using display name
            color = self._generate_color(display_name)
            cr.set_source_rgb(*color)

            # Filter history to the time window
            relevant_history = [net for net in history if net.timestamp >= start_time]

            if len(relevant_history) < 1:
                continue

            # Draw line or point
            if len(relevant_history) == 1:
                # Draw a single point for networks with only one data point
                network = relevant_history[0]
                time_progress = (network.timestamp - start_time).total_seconds() / (
                    self.history_minutes * 60
                )
                signal_progress = self._signal_to_progress(network.signal_level)

                point_x = x + time_progress * width
                point_y = y + height - (signal_progress * height)

                # Draw a circle for single point with increased size
                cr.arc(
                    point_x, point_y, 4, 0, 2 * math.pi
                )  # Increased from 3 to 4 for better visibility
                cr.fill()
            else:
                # Draw line for networks with multiple data points
                first_point = True
                for network in relevant_history:
                    # Calculate position
                    time_progress = (network.timestamp - start_time).total_seconds() / (
                        self.history_minutes * 60
                    )
                    signal_progress = self._signal_to_progress(network.signal_level)

                    point_x = x + time_progress * width
                    point_y = y + height - (signal_progress * height)

                    if first_point:
                        cr.move_to(point_x, point_y)
                        first_point = False
                    else:
                        cr.line_to(point_x, point_y)

                cr.stroke()

                # Also draw points on the line for better visibility
                for network in relevant_history:
                    time_progress = (network.timestamp - start_time).total_seconds() / (
                        self.history_minutes * 60
                    )
                    signal_progress = self._signal_to_progress(network.signal_level)
                    point_x = x + time_progress * width
                    point_y = y + height - (signal_progress * height)
                    cr.arc(
                        point_x, point_y, 3, 0, 2 * math.pi
                    )  # Increased from 2 to 3 for better visibility
                    cr.fill()

    def _signal_to_progress(self, signal_level):
        """Convert signal level to 0-1 progress for chart positioning"""
        # Map 100% (excellent) to 1.0 and 0% (very poor) to 0.0
        # Signal level is now in 0-100 percentage scale from nmcli
        min_signal = 0
        max_signal = 100

        # Add small padding to prevent points from being at exact edges
        # This ensures points at 0% and 100% are still detectable by mouse hover
        padding = 0.02  # 2% padding from edges

        if signal_level >= max_signal:
            return 1.0 - padding
        elif signal_level <= min_signal:
            return padding
        else:
            # Scale to use the middle range, leaving padding at top and bottom
            scaled = signal_level / 100.0
            return padding + scaled * (1.0 - 2 * padding)

    def _draw_legend(self, cr, width, height, margin_top):
        """Draw legend showing network colors and names"""
        if not self.data:
            return

        # Position legend on the left side
        legend_x = 10
        legend_y = margin_top + 10
        line_height = 14  # Reduced for more networks

        # Sort networks by current signal strength for legend (0-100 scale, higher is better)
        sorted_networks = sorted(
            self.data.items(),
            key=lambda item: item[1][-1].signal_level if item[1] else 0,
            reverse=True,
        )

        networks_to_show = sorted_networks[: self.max_networks]

        # Calculate layout for 50 networks - use multiple columns
        max_rows_per_column = 25  # Show up to 25 networks per column
        num_columns = min(
            2, (len(networks_to_show) + max_rows_per_column - 1) // max_rows_per_column
        )
        column_width = 110
        legend_width = column_width * num_columns + 20
        legend_height = (
            min(len(networks_to_show), max_rows_per_column) * line_height + 35
        )

        # Draw legend background with dark theme
        cr.set_source_rgba(0.2, 0.2, 0.2, 0.95)  # Dark semi-transparent background
        cr.rectangle(legend_x, legend_y, legend_width, legend_height)
        cr.fill()

        # Draw legend border
        cr.set_source_rgb(0.5, 0.5, 0.5)  # Gray border for dark theme
        cr.set_line_width(1)
        cr.rectangle(legend_x, legend_y, legend_width, legend_height)
        cr.stroke()

        # Draw title
        cr.set_source_rgb(0.9, 0.9, 0.9)  # Light text
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(11)
        cr.move_to(legend_x + 10, legend_y + 18)
        cr.show_text("WiFi Networks")

        # Draw legend items
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(8)  # Smaller font for more networks

        for i, (network_key, history) in enumerate(networks_to_show):
            # Calculate position for multi-column layout
            column = i // max_rows_per_column
            row = i % max_rows_per_column
            current_x = legend_x + 10 + column * column_width
            current_y = legend_y + 30 + row * line_height

            # Get display name for the network
            network = history[-1]  # Get latest network data
            if network.ssid and network.ssid != "Hidden Network":
                display_name = network.ssid
            else:
                display_name = f"Hidden-{network.bssid[-8:]}"

            # Draw color line
            color = self._generate_color(display_name)
            cr.set_source_rgb(*color)
            cr.set_line_width(2)
            cr.move_to(current_x, current_y + 5)
            cr.line_to(current_x + 10, current_y + 5)
            cr.stroke()

            # Draw network name and signal with light text for dark theme
            cr.set_source_rgb(0.9, 0.9, 0.9)  # Light text for dark background
            current_signal = history[-1].signal_level if history else 0

            # Adjust text length for multi-column layout
            max_chars = 12
            short_name = display_name[:max_chars] + (
                "..." if len(display_name) > max_chars else ""
            )
            text = f"{short_name} ({current_signal}%)"

            cr.move_to(current_x + 13, current_y + 8)
            cr.show_text(text)

    def _on_mouse_motion(self, controller, x, y):
        """Handle mouse motion for network name tooltip"""
        # Convert mouse coordinates to chart coordinates
        margin_left = 250
        margin_right = 80
        margin_top = 30
        margin_bottom = 60

        width = self.get_width()
        height = self.get_height()
        chart_width = width - margin_left - margin_right
        chart_height = height - margin_top - margin_bottom

        # Check if mouse is within chart area
        if (
            margin_left <= x <= margin_left + chart_width
            and margin_top <= y <= margin_top + chart_height
        ):
            # Find closest network line
            closest_network = self._find_closest_network(
                x, y, margin_left, margin_top, chart_width, chart_height
            )

            if closest_network != self.hover_network:
                self.hover_network = closest_network
                self.hover_x = x
                self.hover_y = y
                self.queue_draw()  # Redraw to show tooltip
        else:
            if self.hover_network:
                self.hover_network = None
                self.queue_draw()

    def _on_mouse_leave(self, controller):
        """Handle mouse leaving the chart area"""
        if self.hover_network:
            self.hover_network = None
            self.queue_draw()

    def _find_closest_network(
        self, mouse_x, mouse_y, chart_x, chart_y, chart_width, chart_height
    ):
        """Find the network line closest to the mouse cursor"""
        if not self.data:
            return None

        min_distance = float("inf")
        closest_network = None

        now = datetime.now()
        start_time = now - timedelta(minutes=self.history_minutes)

        # Check each network
        sorted_networks = sorted(
            self.data.items(),
            key=lambda item: item[1][-1].signal_level if item[1] else 0,
            reverse=True,
        )

        networks_to_check = sorted_networks[: self.max_networks]

        for network_key, history in networks_to_check:
            if not history:
                continue

            relevant_history = [net for net in history if net.timestamp >= start_time]
            if len(relevant_history) < 1:
                continue

            # Check distance to each point in the line
            for network in relevant_history:
                time_progress = (network.timestamp - start_time).total_seconds() / (
                    self.history_minutes * 60
                )
                signal_progress = network.signal_level / 100.0

                point_x = chart_x + time_progress * chart_width
                point_y = chart_y + chart_height - (signal_progress * chart_height)

                # Calculate distance from mouse to this point
                distance = ((mouse_x - point_x) ** 2 + (mouse_y - point_y) ** 2) ** 0.5

                if distance < min_distance and distance < 20:  # Within 20 pixels
                    min_distance = distance
                    # Get display name and BSSID
                    network_data = history[-1]
                    if network_data.ssid and network_data.ssid != "Hidden Network":
                        closest_network = f"{network_data.ssid}\n{network_data.bssid}"
                    else:
                        closest_network = f"Hidden Network\n{network_data.bssid}"

        return closest_network

    def _draw_tooltip(self, cr, width, height):
        """Draw tooltip showing network name and BSSID on hover"""
        if not self.hover_network:
            return

        # Create tooltip text from hover_network
        tooltip_lines = []

        if isinstance(self.hover_network, list):
            # Multiple networks case
            if len(self.hover_network) > 1:
                tooltip_lines.append("Networks with similar signal strength:")
                tooltip_lines.append("")  # Empty line for spacing

                for network in self.hover_network:
                    tooltip_lines.append(f"• {network['ssid']}")
                    tooltip_lines.append(f"  BSSID: {network['bssid']}")
                    tooltip_lines.append(f"  Signal: {network['signal']}%")
                    tooltip_lines.append("")  # Empty line between networks

                # Remove last empty line
                if tooltip_lines and tooltip_lines[-1] == "":
                    tooltip_lines.pop()
            else:
                # Single network in list
                network = self.hover_network[0]
                tooltip_lines = [
                    network["ssid"],
                    f"BSSID: {network['bssid']}",
                    f"Signal: {network['signal']}%",
                ]
        elif isinstance(self.hover_network, dict):
            # Single network case
            tooltip_lines = [
                self.hover_network["ssid"],
                f"BSSID: {self.hover_network['bssid']}",
                f"Signal: {self.hover_network['signal']}%",
            ]
        else:
            # Fallback for string format
            tooltip_lines = str(self.hover_network).split("\n")

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(11)  # Slightly smaller font for multiple networks

        # Calculate dimensions for multi-line text
        max_width = 0
        line_height = 15
        total_height = len(tooltip_lines) * line_height

        for line in tooltip_lines:
            text_extents = cr.text_extents(line)
            max_width = max(max_width, text_extents.width)

        padding = 10
        tooltip_width = max_width + 2 * padding
        tooltip_height = total_height + 2 * padding

        # Position tooltip near mouse, but keep it within bounds
        tooltip_x = min(self.hover_x + 15, width - tooltip_width - 5)
        tooltip_y = max(self.hover_y - tooltip_height - 15, 5)

        # Draw tooltip background with semi-transparent dark background
        cr.set_source_rgba(0.1, 0.1, 0.1, 0.95)
        cr.rectangle(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
        cr.fill()

        # Draw tooltip border
        cr.set_source_rgba(0.8, 0.8, 0.8, 0.9)
        cr.set_line_width(1)
        cr.rectangle(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
        cr.stroke()

        # Draw tooltip text (multi-line)
        cr.set_source_rgb(1.0, 1.0, 1.0)  # White text
        for i, line in enumerate(tooltip_lines):
            y_offset = tooltip_y + padding + (i + 1) * line_height - 2
            cr.move_to(tooltip_x + padding, y_offset)
            cr.show_text(line)

    def _on_mouse_motion(self, controller, x, y):
        """Handle mouse motion for network tooltip"""
        # Convert mouse coordinates to chart coordinates
        margin_left = 80
        margin_right = 40
        margin_top = 40
        margin_bottom = 80

        width = self.get_width()
        height = self.get_height()
        chart_width = width - margin_left - margin_right
        chart_height = height - margin_top - margin_bottom

        # Check if mouse is within chart area
        if (
            margin_left <= x <= margin_left + chart_width
            and margin_top <= y <= margin_top + chart_height
        ):
            # Find network under mouse
            network_info = self._find_network_at_position(
                x, y, margin_left, margin_top, chart_width, chart_height
            )

            if network_info != self.hover_network:
                self.hover_network = network_info
                self.hover_x = x
                self.hover_y = y
                self.queue_draw()
        else:
            if self.hover_network:
                self.hover_network = None
                self.queue_draw()

    def _on_mouse_leave(self, controller):
        """Handle mouse leaving the chart area"""
        if self.hover_network:
            self.hover_network = None
            self.queue_draw()

    def _find_network_at_position(
        self, mouse_x, mouse_y, chart_x, chart_y, chart_width, chart_height
    ):
        """Find the network under the mouse cursor in signal strength chart"""
        if not self.data:
            return None

        # Calculate time position from mouse X coordinate
        now = datetime.now()
        start_time = now - timedelta(minutes=self.history_minutes)

        # Find all networks within tolerance
        candidate_networks = []
        tolerance = 25  # Increased from 20 to 25 pixels for better edge detection

        for network_key, history in self.data.items():
            if not history:
                continue

            # Get display name for the network
            network = history[-1]
            if network.ssid and network.ssid != "Hidden Network":
                display_name = network.ssid
            else:
                display_name = f"Hidden-{network.bssid[-8:]}"

            # Filter history to the time window
            relevant_history = [net for net in history if net.timestamp >= start_time]

            if not relevant_history:
                continue

            # Check each point in the history
            for net_point in relevant_history:
                # Calculate point position
                point_time_progress = (
                    net_point.timestamp - start_time
                ).total_seconds() / (self.history_minutes * 60)
                point_signal_progress = self._signal_to_progress(net_point.signal_level)

                point_x = chart_x + point_time_progress * chart_width
                point_y = (
                    chart_y + chart_height - (point_signal_progress * chart_height)
                )

                # Calculate distance from mouse to this point
                distance = math.sqrt(
                    (mouse_x - point_x) ** 2 + (mouse_y - point_y) ** 2
                )

                if distance < tolerance:
                    candidate_networks.append({
                        "network_key": network_key,
                        "ssid": display_name,
                        "bssid": net_point.bssid,
                        "signal": net_point.signal_level,
                        "timestamp": net_point.timestamp,
                        "distance": distance,
                    })

            # Also check line segments between points if there are multiple points
            if len(relevant_history) > 1:
                for i in range(len(relevant_history) - 1):
                    point1 = relevant_history[i]
                    point2 = relevant_history[i + 1]

                    # Calculate positions for both points
                    time1_progress = (point1.timestamp - start_time).total_seconds() / (
                        self.history_minutes * 60
                    )
                    signal1_progress = self._signal_to_progress(point1.signal_level)
                    x1 = chart_x + time1_progress * chart_width
                    y1 = chart_y + chart_height - (signal1_progress * chart_height)

                    time2_progress = (point2.timestamp - start_time).total_seconds() / (
                        self.history_minutes * 60
                    )
                    signal2_progress = self._signal_to_progress(point2.signal_level)
                    x2 = chart_x + time2_progress * chart_width
                    y2 = chart_y + chart_height - (signal2_progress * chart_height)

                    # Calculate distance from mouse to line segment
                    line_distance = self._point_to_line_distance(
                        mouse_x, mouse_y, x1, y1, x2, y2
                    )

                    if line_distance < tolerance:
                        # Use the closest point on the line for network info
                        closer_point = (
                            point1 if abs(mouse_x - x1) < abs(mouse_x - x2) else point2
                        )
                        candidate_networks.append({
                            "network_key": network_key,
                            "ssid": display_name,
                            "bssid": closer_point.bssid,
                            "signal": closer_point.signal_level,
                            "timestamp": closer_point.timestamp,
                            "distance": line_distance,
                        })

        # If no candidates found, return None
        if not candidate_networks:
            return None

        # Find the closest network
        closest_network = min(candidate_networks, key=lambda x: x["distance"])
        closest_signal = closest_network["signal"]

        # Filter networks with signal strength within 4% of the closest
        signal_threshold = 4
        networks_in_range = []

        for network in candidate_networks:
            if abs(network["signal"] - closest_signal) <= signal_threshold:
                networks_in_range.append(network)

        # Remove duplicates based on network_key (same network might appear multiple times from different time points)
        unique_networks = {}
        for network in networks_in_range:
            key = network["network_key"]
            if (
                key not in unique_networks
                or network["distance"] < unique_networks[key]["distance"]
            ):
                unique_networks[key] = network

        # Convert back to list and sort by signal strength (strongest first)
        result_networks = list(unique_networks.values())
        result_networks.sort(key=lambda x: x["signal"], reverse=True)

        # Return single network or multiple networks depending on count
        if len(result_networks) == 1:
            return result_networks[0]
        else:
            return result_networks

    def _point_to_line_distance(self, px, py, x1, y1, x2, y2):
        """Calculate the shortest distance from a point to a line segment"""
        # Calculate the line segment length squared
        line_length_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2

        # If the line segment has zero length, return distance to either endpoint
        if line_length_sq == 0:
            return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)

        # Calculate the projection of the point onto the line
        t = max(
            0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_length_sq)
        )

        # Calculate the closest point on the line segment
        closest_x = x1 + t * (x2 - x1)
        closest_y = y1 + t * (y2 - y1)

        # Return the distance from the point to the closest point on the line segment
        return math.sqrt((px - closest_x) ** 2 + (py - closest_y) ** 2)


class WiFiAnalyzerView(Gtk.Box):
    """Main WiFi Analyzer view with charts and controls"""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        # Ensure proper layout behavior for header/content separation
        self.set_vexpand(True)
        self.set_hexpand(True)

        self.scanner = WiFiScanner()
        self.update_timeout_id = None
        self.show_hidden_networks = False
        self.previously_seen_networks = (
            set()
        )  # Track networks that have been seen before
        self.is_monitoring = False  # Track if monitoring is active

        self._build_ui()
        self._connect_signals()

        # Configure scanner but don't start automatically
        self.scanner.set_scan_interval(1.0)
        self.scanner.add_callback(self._on_wifi_data_updated)

    def _build_ui(self):
        """Build the user interface"""
        # Charts container - includes header and charts, all scrollable
        charts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        charts_box.set_margin_top(12)
        charts_box.set_margin_bottom(12)
        charts_box.set_margin_start(12)
        charts_box.set_margin_end(12)

        # Header with controls - now scrolls with content
        header = self._create_header()
        charts_box.append(header)

        # Signal strength chart
        signal_frame = Adw.PreferencesGroup()
        signal_frame.set_title(_("Signal strength (last 2 minutes)"))

        self.signal_chart = SignalStrengthChart()
        signal_frame.add(self.signal_chart)
        charts_box.append(signal_frame)

        # Channel usage chart
        channel_frame = Adw.PreferencesGroup()
        self.channel_chart = ChannelUsageTable()
        channel_frame.add(self.channel_chart)
        charts_box.append(channel_frame)

        # Wrap everything in scrolled window - header and charts scroll together
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_child(charts_box)

        self.append(scrolled)

    def _create_header(self):
        """Create header with controls"""
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.add_css_class("toolbar")
        header.set_margin_top(12)
        header.set_margin_bottom(6)
        header.set_margin_start(12)
        header.set_margin_end(12)

        # Ensure header stays fixed and doesn't expand
        header.set_vexpand(False)
        header.set_hexpand(True)
        header.set_valign(Gtk.Align.START)

        # Scan status
        self.status_label = Gtk.Label(label=_("Ready to scan"))
        self.status_label.add_css_class("dim-label")
        self.status_label.set_hexpand(False)
        header.append(self.status_label)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)

        # Hidden networks toggle
        hidden_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hidden_box.set_hexpand(False)

        hidden_label = Gtk.Label(label=_("Show hidden networks:"))
        hidden_box.append(hidden_label)

        self.hidden_switch = Gtk.Switch()
        self.hidden_switch.set_active(False)
        self.hidden_switch.connect("notify::active", self._on_hidden_switch_toggled)
        hidden_box.append(self.hidden_switch)

        header.append(hidden_box)

        return header

    def _connect_signals(self):
        """Connect signals"""
        pass

    def _on_hidden_switch_toggled(self, switch, pspec):
        """Handle hidden networks switch toggle"""
        self.show_hidden_networks = switch.get_active()
        # Trigger an immediate UI update with current data
        self._update_charts()

    def _update_charts(self):
        """Update charts with current data, respecting hidden networks setting"""
        # Get current data
        history_data = self.scanner.get_all_history(minutes=2)
        channel_usage = self.scanner.get_channel_usage()

        # Track currently seen networks (for other purposes if needed)
        current_network_keys = set(history_data.keys())
        self.previously_seen_networks.update(current_network_keys)

        # Filter data if hidden networks should be hidden
        if not self.show_hidden_networks:
            # Filter history_data to exclude hidden networks
            filtered_history = {}
            for network_key, history in history_data.items():
                if history:
                    latest_network = history[-1]
                    # Only include if it has a visible SSID
                    if (
                        latest_network.ssid
                        and latest_network.ssid.strip()
                        and latest_network.ssid != "Hidden Network"
                    ):
                        filtered_history[network_key] = history
            history_data = filtered_history

            # Filter channel_usage to exclude hidden networks
            filtered_channel_usage = {}
            for channel, network_names in channel_usage.items():
                filtered_names = [
                    name for name in network_names if not name.startswith("Hidden")
                ]
                if filtered_names:
                    filtered_channel_usage[channel] = filtered_names
            channel_usage = filtered_channel_usage

        # Update charts
        self.signal_chart.update_data(history_data)
        self.channel_chart.update_data(channel_usage, history_data)

    def _on_wifi_data_updated(self, current_networks, channel_usage):
        """Handle updated WiFi data"""

        def update_ui():
            # Update charts with filtering applied
            self._update_charts()

            # Update status (count all networks, regardless of hidden setting)
            all_networks = self.scanner.get_current_networks()
            network_count = len(all_networks)
            self.status_label.set_text(_("Found {} networks").format(network_count))

            return False

        # Schedule UI update on main thread
        GLib.idle_add(update_ui)

    def start_monitoring(self):
        """Start WiFi monitoring"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.scanner.start_scanning()
            self.status_label.set_text(_("Scanning..."))

    def stop_monitoring(self):
        """Stop WiFi monitoring"""
        if self.is_monitoring:
            self.is_monitoring = False
            self.scanner.stop_scanning()
            self.status_label.set_text(_("Monitoring stopped"))

    def is_monitoring_active(self):
        """Check if monitoring is currently active"""
        return self.is_monitoring

    def cleanup(self):
        """Clean up resources"""
        if self.scanner:
            self.scanner.stop_scanning()
