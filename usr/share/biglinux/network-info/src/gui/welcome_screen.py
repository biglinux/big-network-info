"""
Welcome screen component for the Big Network Info application.
Provides an overview of features and allows users to configure startup behavior.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Pango
from .translation import _
from ..core.config import ConfigManager


class WelcomeScreen(Adw.Window):
    """Welcome screen dialog showing application features and startup options."""

    def __init__(self, parent: Gtk.Window, config_manager: ConfigManager):
        """
        Initialize the welcome screen.

        Args:
            parent: Parent window
            config_manager: Configuration manager instance
        """
        super().__init__()
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title("Big Network Info")
        self.set_default_size(800, 600)
        self.set_resizable(True)

        self.config_manager = config_manager
        self.parent_window = parent

        # Setup the UI
        self.setup_ui()

        # Load the "show on startup" preference
        self.load_startup_preference()

    def setup_ui(self) -> None:
        """Setup the welcome screen UI."""
        # Add header bar with close button
        header_bar = Adw.HeaderBar()
        header_bar.set_show_end_title_buttons(True)
        header_bar.set_title_widget(Gtk.Label(label="Big Network Info"))
        header_bar.add_css_class("flat")  # Remove separator line

        # Main container with header bar
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.append(header_bar)
        self.set_content(main_box)

        # Scrolled window for content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        main_box.append(scrolled)

        # Content container
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content_box.set_margin_bottom(15)
        scrolled.set_child(content_box)

        # Features section in a more compact layout
        self.create_features_section(content_box)

        # Bottom section with preferences and buttons
        self.create_bottom_section(content_box)

    def create_features_section(self, parent: Gtk.Box) -> None:
        """Create the features section with 2x2 grid layout."""
        # Features in a 2x2 grid layout
        features_grid = Gtk.Grid()
        features_grid.set_column_homogeneous(True)
        features_grid.set_row_homogeneous(True)
        features_grid.set_hexpand(True)
        features_grid.set_vexpand(True)

        # Create feature items
        features = [
            (
                "network-wireless-symbolic",
                _("Network Diagnostics"),
                _(
                    "Test your internet connection, DNS servers, network connectivity, and analyze WiFi networks"
                ),
            ),
            (
                "computer-symbolic",
                _("Device Discovery"),
                _("Find all devices on your network with detailed information"),
            ),
            (
                "applications-network-symbolic",
                _("Service Detection"),
                _("Identify running services like web servers, SSH, and databases"),
            ),
            (
                "document-save-symbolic",
                _("Export Reports"),
                _("Save detailed scan results and generate professional reports"),
            ),
        ]

        # Position features in 2x2 grid
        positions = [(0, 0), (1, 0), (0, 1), (1, 1)]

        for i, (icon, title, description) in enumerate(features):
            row, col = positions[i]
            feature_item = self.create_grid_feature_item(icon, title, description)
            features_grid.attach(feature_item, col, row, 1, 1)

        parent.append(features_grid)

    def create_grid_feature_item(
        self, icon_name: str, title: str, description: str
    ) -> Gtk.Widget:
        """Create a feature item for grid layout."""
        item_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        item_box.add_css_class("card")
        item_box.set_margin_start(24)
        item_box.set_margin_end(24)
        item_box.set_margin_top(24)
        item_box.set_margin_bottom(12)
        item_box.set_hexpand(True)
        item_box.set_vexpand(True)
        item_box.set_valign(Gtk.Align.CENTER)

        # Create inner container with padding
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)

        # Icon
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(40)
        icon.add_css_class("accent")
        icon.set_halign(Gtk.Align.CENTER)
        content_box.append(icon)

        # Title
        title_label = Gtk.Label()
        # Escape HTML entities in title for markup
        escaped_title = title.replace("&", "&amp;")
        title_label.set_markup(
            f"<span weight='bold' size='large'>{escaped_title}</span>"
        )
        title_label.set_halign(Gtk.Align.CENTER)
        title_label.set_wrap(True)
        title_label.set_justify(Gtk.Justification.CENTER)
        content_box.append(title_label)

        # Description
        desc_label = Gtk.Label()
        desc_label.set_text(description)
        desc_label.set_halign(Gtk.Align.CENTER)
        desc_label.set_wrap(True)
        desc_label.set_wrap_mode(Gtk.WrapMode.WORD)
        desc_label.set_justify(Gtk.Justification.CENTER)
        desc_label.add_css_class("dim-label")
        desc_label.set_lines(2)
        desc_label.set_ellipsize(Pango.EllipsizeMode.END)
        desc_label.set_max_width_chars(40)
        content_box.append(desc_label)

        # Add content to item box
        item_box.append(content_box)

        return item_box

    def create_bottom_section(self, parent: Gtk.Box) -> None:
        """Create the bottom section with preferences and buttons."""
        # Bottom container
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        bottom_box.set_halign(Gtk.Align.CENTER)

        # Startup preference
        startup_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        startup_box.set_halign(Gtk.Align.CENTER)

        startup_label = Gtk.Label()
        startup_label.set_text(_("Show this welcome screen on startup"))
        startup_box.append(startup_label)

        self.startup_switch = Gtk.Switch()
        self.startup_switch.connect("notify::active", self.on_startup_switch_toggled)
        startup_box.append(self.startup_switch)

        bottom_box.append(startup_box)

        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)

        # Start Exploring button
        start_btn = Gtk.Button()
        start_btn.set_label(_("Let's Start"))
        start_btn.add_css_class("suggested-action")
        start_btn.connect("clicked", self.on_get_started_clicked)
        button_box.append(start_btn)

        bottom_box.append(button_box)
        parent.append(bottom_box)

    def load_startup_preference(self) -> None:
        """Load the startup preference from configuration."""
        show_on_startup = self.config_manager.get_setting(
            "show_welcome_on_startup", True
        )
        self.startup_switch.set_active(show_on_startup)

    def on_startup_switch_toggled(self, switch: Gtk.Switch, *args) -> None:
        """Handle startup switch toggle."""
        show_on_startup = switch.get_active()
        self.config_manager.set_setting("show_welcome_on_startup", show_on_startup)
        self.config_manager.save_config()

    def on_get_started_clicked(self, button: Gtk.Button) -> None:
        """Handle Get Started button click."""
        # Start with the diagnostics tab
        if hasattr(self.parent_window, "activate_tab"):
            self.parent_window.activate_tab("diagnostics")
        self.close()

    @staticmethod
    def should_show_on_startup(config_manager: ConfigManager) -> bool:
        """
        Check if the welcome screen should be shown on startup.

        Args:
            config_manager: Configuration manager instance

        Returns:
            True if welcome screen should be shown
        """
        return config_manager.get_setting("show_welcome_on_startup", True)

    @staticmethod
    def show_welcome(parent: Gtk.Window, config_manager: ConfigManager) -> None:
        """
        Show the welcome screen.

        Args:
            parent: Parent window
            config_manager: Configuration manager instance
        """
        welcome = WelcomeScreen(parent, config_manager)
        welcome.present()
