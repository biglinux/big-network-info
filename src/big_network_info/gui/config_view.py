"""
Configuration GUI components for managing custom services.
Provides a user-friendly interface for adding, editing, and removing custom services.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from .translation import _

from gi.repository import Gtk, Adw, Gio

from ..core.services import ServiceInfo, COMMON_SERVICES
from ..core.config import ConfigManager


class ConfigurationView(Gtk.ScrolledWindow):
    """Main configuration view with inline service editing."""

    def __init__(self, parent_window: Gtk.Window, config_manager: ConfigManager = None):
        """
        Initialize the configuration view.

        Args:
            parent_window: Parent window reference
            config_manager: Configuration manager instance
        """
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.parent_window = parent_window
        self.config_manager = config_manager or ConfigManager()

        # Track editing state
        self.editing_service = None
        self.edit_group = None
        self.service_rows = {}  # Track service rows to avoid recreation

        # Create width-limited container
        content_clamp = Adw.Clamp()
        content_clamp.set_maximum_size(800)
        content_clamp.set_tightening_threshold(600)
        self.set_child(content_clamp)

        # Main content box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.main_box.set_margin_start(12)
        self.main_box.set_margin_end(12)
        self.main_box.set_margin_top(12)
        self.main_box.set_margin_bottom(12)
        content_clamp.set_child(self.main_box)

        self.setup_ui()
        self.refresh_services()

    def setup_ui(self) -> None:
        """Set up the configuration UI."""
        # Detection Settings section - add this first
        self.create_detection_settings_section()

        # Custom Services section
        self.create_custom_services_section()

        # Built-in Services section
        self.create_builtin_services_section()

        # Import/Export section
        self.create_import_export_section()

    def create_detection_settings_section(self) -> None:
        """Create the detection settings configuration section."""
        # Detection settings group
        self.detection_group = Adw.PreferencesGroup()
        self.detection_group.set_margin_top(12)
        self.detection_group.set_title(_("Host and Service Detection"))
        self.detection_group.set_description(
            _("Configure timeouts and parallel threads for network scanning.")
        )

        # Ping timeout setting
        ping_timeout_row = Adw.SpinRow()
        ping_timeout_row.set_title(_("Ping Timeout"))
        ping_timeout_row.set_subtitle(_("Time to wait for ping response (seconds)"))
        ping_timeout_adjustment = Gtk.Adjustment(
            value=self.config_manager.config.ping_timeout,
            lower=0.1,
            upper=10.0,
            step_increment=0.1,
            page_increment=1.0,
        )
        ping_timeout_row.set_adjustment(ping_timeout_adjustment)
        ping_timeout_row.set_digits(1)
        # Connect spinrow to apply config changes
        ping_timeout_row.connect("notify::value", self.on_ping_timeout_changed)
        self.detection_group.add(ping_timeout_row)

        # Ping attempts setting
        ping_attempts_row = Adw.SpinRow()
        ping_attempts_row.set_title(_("Ping Attempts"))
        ping_attempts_row.set_subtitle(_("Number of ping attempts per host"))
        ping_attempts_adjustment = Gtk.Adjustment(
            value=self.config_manager.config.ping_attempts,
            lower=1,
            upper=10,
            step_increment=1,
            page_increment=1,
        )
        ping_attempts_row.set_adjustment(ping_attempts_adjustment)
        ping_attempts_row.set_digits(0)
        ping_attempts_row.connect("notify::value", self.on_ping_attempts_changed)
        self.detection_group.add(ping_attempts_row)

        # Hostname resolution timeout setting
        hostname_timeout_row = Adw.SpinRow()
        hostname_timeout_row.set_title(_("Hostname Resolution Timeout"))
        hostname_timeout_row.set_subtitle(
            _("Time to wait for hostname lookup (seconds)")
        )
        hostname_timeout_adjustment = Gtk.Adjustment(
            value=self.config_manager.config.hostname_timeout,
            lower=0.1,
            upper=5.0,
            step_increment=0.1,
            page_increment=0.5,
        )
        hostname_timeout_row.set_adjustment(hostname_timeout_adjustment)
        hostname_timeout_row.set_digits(1)
        hostname_timeout_row.connect("notify::value", self.on_hostname_timeout_changed)
        self.detection_group.add(hostname_timeout_row)

        # Discovery threads setting
        discovery_threads_row = Adw.SpinRow()
        discovery_threads_row.set_title(_("Discovery Threads"))
        discovery_threads_row.set_subtitle(_("Parallel threads for host discovery"))
        discovery_threads_adjustment = Gtk.Adjustment(
            value=self.config_manager.config.discovery_threads,
            lower=1,
            upper=255,
            step_increment=10,
            page_increment=25,
        )
        discovery_threads_row.set_adjustment(discovery_threads_adjustment)
        discovery_threads_row.set_digits(0)
        discovery_threads_row.connect(
            "notify::value", self.on_discovery_threads_changed
        )
        self.detection_group.add(discovery_threads_row)

        # Port scan timeout setting
        scan_timeout_row = Adw.SpinRow()
        scan_timeout_row.set_title(_("Port Scan Timeout"))
        scan_timeout_row.set_subtitle(_("Time to wait for port connection (seconds)"))
        scan_timeout_adjustment = Gtk.Adjustment(
            value=self.config_manager.config.scan_timeout,
            lower=0.1,
            upper=5.0,
            step_increment=0.1,
            page_increment=0.5,
        )
        scan_timeout_row.set_adjustment(scan_timeout_adjustment)
        scan_timeout_row.set_digits(1)
        scan_timeout_row.connect("notify::value", self.on_scan_timeout_changed)
        self.detection_group.add(scan_timeout_row)

        # Scan threads setting
        scan_threads_row = Adw.SpinRow()
        scan_threads_row.set_title(_("Port Scan Threads"))
        scan_threads_row.set_subtitle(_("Parallel threads for port scanning"))
        scan_threads_adjustment = Gtk.Adjustment(
            value=self.config_manager.config.scan_threads,
            lower=1,
            upper=255,
            step_increment=10,
            page_increment=25,
        )
        scan_threads_row.set_adjustment(scan_threads_adjustment)
        scan_threads_row.set_digits(0)
        # Update scan_threads when spinrow value changes
        # Connect spinrow directly to catch value changes
        scan_threads_row.connect("notify::value", self.on_scan_threads_changed)
        self.detection_group.add(scan_threads_row)

        self.main_box.append(self.detection_group)

    def create_custom_services_section(self) -> None:
        """Create the custom services management section."""
        # Header with add button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_box.set_margin_bottom(6)

        # Custom services group
        self.custom_services_group = Adw.PreferencesGroup()
        self.custom_services_group.set_margin_top(24)
        self.custom_services_group.set_title(_("Your Custom Services"))
        self.custom_services_group.set_description(
            _(
                "Services you've added for scanning. These will be checked on all discovered devices."
            )
        )
        self.main_box.append(self.custom_services_group)

        add_button = Gtk.Button(label=_("Add Service"))
        add_button.add_css_class("suggested-action")
        add_button.set_icon_name("list-add-symbolic")
        add_button.connect("clicked", self.on_add_service)
        header_box.append(add_button)

        clear_button = Gtk.Button(label=_("Clear All"))
        clear_button.add_css_class("destructive-action")
        clear_button.connect("clicked", self.on_clear_all_services)
        header_box.append(clear_button)

        self.main_box.append(header_box)

    def create_builtin_services_section(self) -> None:
        """Create the built-in services display section."""
        # Built-in services group
        self.builtin_services_group = Adw.PreferencesGroup()
        self.builtin_services_group.set_margin_top(24)
        self.builtin_services_group.set_title(_("Standard Network Services"))
        self.builtin_services_group.set_description(
            _("Common services that are automatically scanned on all devices.")
        )

        # Show all built-in services
        for service in COMMON_SERVICES:
            row = Adw.ActionRow()
            row.set_title(f"{service.name} ({service.port}/{service.protocol})")
            row.set_subtitle(service.description)

            # Add service icon
            icon = Gtk.Image.new_from_icon_name(
                self.get_service_icon(service.access_method)
            )
            row.add_prefix(icon)

            self.builtin_services_group.add(row)

        self.main_box.append(self.builtin_services_group)

    def create_import_export_section(self) -> None:
        """Create the import/export section."""
        # Import/Export group
        io_group = Adw.PreferencesGroup()
        io_group.set_margin_top(24)
        io_group.set_title(_("Service Configuration"))
        io_group.set_description(
            _("Save your custom services to a file or load services from a backup.")
        )

        # Export row
        export_row = Adw.ActionRow()
        export_row.set_title(_("Export Custom Services"))
        export_row.set_subtitle(_("Save your custom services to a JSON file"))

        export_button = Gtk.Button(label=_("Export"))
        export_button.set_valign(Gtk.Align.CENTER)
        export_button.connect("clicked", self.on_export_services)
        export_row.add_suffix(export_button)

        io_group.add(export_row)

        # Import row
        import_row = Adw.ActionRow()
        import_row.set_title(_("Import Custom Services"))
        import_row.set_subtitle(_("Load custom services from a JSON file"))

        import_button = Gtk.Button(label=_("Import"))
        import_button.set_valign(Gtk.Align.CENTER)
        import_button.connect("clicked", self.on_import_services)
        import_row.add_suffix(import_button)

        io_group.add(import_row)

        self.main_box.append(io_group)

    def get_service_icon(self, access_method: str) -> str:
        """Get icon name for service access method."""
        icons = {
            "http": "emblem-web-symbolic",
            "https": "emblem-web-symbolic",
            "ssh": "utilities-terminal-symbolic",
            "ftp": "folder-remote-symbolic",
            "smb": "folder-remote-symbolic",
            "rdp": "computer-symbolic",
            "vnc": "computer-symbolic",
        }
        return icons.get(access_method, "network-server-symbolic")

    def refresh_services(self) -> None:
        """Refresh the services display."""
        self.refresh_custom_services()

    def refresh_custom_services(self) -> None:
        """Refresh the custom services list without destroying edit forms."""
        custom_services = self.config_manager.get_custom_services()
        print("DEBUG: refresh_custom_services called")
        print(f"DEBUG: Got {len(custom_services)} custom services from config manager")
        print(f"DEBUG: Custom services: {[{s.name: s.port} for s in custom_services]}")

        # Clear all existing service rows and rebuild to ensure consistency
        # Keep only the empty state row and edit form if they exist
        keys_to_remove = [k for k in self.service_rows.keys() if k != "__empty__"]
        for key in keys_to_remove:
            row = self.service_rows[key]
            if row.get_parent() == self.custom_services_group:
                self.custom_services_group.remove(row)
            del self.service_rows[key]

        # Add all current services
        for service in custom_services:
            key = (service.port, service.protocol, service.name)
            row = self.create_custom_service_row(service)
            self.service_rows[key] = row
            self.custom_services_group.add(row)

        # Handle empty state
        if not custom_services:
            # Only add empty state row if no edit form is shown and no empty row exists
            if self.editing_service is None and "__empty__" not in self.service_rows:
                no_services_row = Adw.ActionRow()
                no_services_row.set_title(_("No custom services configured"))
                no_services_row.set_subtitle(
                    _("Click 'Add Service' to create your first custom service")
                )
                no_services_row.add_css_class("dim-label")
                # Store with special key for easy removal
                self.service_rows["__empty__"] = no_services_row
                self.custom_services_group.add(no_services_row)
        else:
            # Remove empty state if it exists
            if "__empty__" in self.service_rows:
                empty_row = self.service_rows["__empty__"]
                if empty_row.get_parent() == self.custom_services_group:
                    self.custom_services_group.remove(empty_row)
                del self.service_rows["__empty__"]

        # Show edit form if needed
        if self.editing_service is not None:
            self.show_edit_form()

        # Update button visibility for all rows after editing state changes
        for key, row in self.service_rows.items():
            if key != "__empty__" and hasattr(row, "service"):
                self.update_row_button_visibility(row)

    def create_custom_service_row(self, service: ServiceInfo) -> Adw.ActionRow:
        """Create a row for a custom service."""
        row = Adw.ActionRow()
        row.set_title(f"{service.name} ({service.port}/{service.protocol})")
        row.set_subtitle(service.description)

        # Add icon
        if service.access_method:
            icon = Gtk.Image.new_from_icon_name(
                self.get_service_icon(service.access_method)
            )
            row.add_prefix(icon)

        # Store service reference in row for easy access
        row.service = service

        # Create button container
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Edit button
        edit_button = Gtk.Button()
        edit_button.set_icon_name("document-edit-symbolic")
        edit_button.set_tooltip_text(_("Edit service"))
        edit_button.add_css_class("flat")
        edit_button.connect("clicked", lambda btn: self.on_edit_service(service))
        button_box.append(edit_button)

        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name("user-trash-symbolic")
        delete_button.set_tooltip_text(_("Delete service"))
        delete_button.add_css_class("flat")
        delete_button.connect("clicked", lambda btn: self.on_delete_service(service))
        button_box.append(delete_button)

        # Store button references for visibility control
        row.edit_button = edit_button
        row.delete_button = delete_button
        row.button_box = button_box

        row.add_suffix(button_box)

        # Set initial button visibility
        self.update_row_button_visibility(row)

        return row

    def update_row_button_visibility(self, row: Adw.ActionRow) -> None:
        """Update button visibility for a specific row based on editing state."""
        if hasattr(row, "service") and hasattr(row, "button_box"):
            # Hide buttons if we're editing this specific service
            is_editing_this_service = self.editing_service == row.service
            row.button_box.set_visible(not is_editing_this_service)

    def show_edit_form(self) -> None:
        """Show inline edit form for the service being edited."""
        # Only create edit form if it doesn't exist or isn't attached
        if self.edit_group is None or self.edit_group.get_parent() is None:
            self.create_edit_form()

        # Populate fields if editing existing service
        if self.editing_service and self.editing_service != "new":
            self.populate_edit_fields(self.editing_service)

    def create_edit_form(self) -> None:
        """Create the edit form widget."""
        # Clean up any existing edit form
        if self.edit_group and self.edit_group.get_parent():
            self.edit_group.get_parent().remove(self.edit_group)

        self.edit_group = Adw.PreferencesGroup()
        self.edit_group.set_title(
            _("Edit Service") if self.editing_service != "new" else _("Add New Service")
        )
        self.edit_group.set_margin_top(12)

        # Service name
        self.name_row = Adw.EntryRow()
        self.name_row.set_title(_("Service Name"))
        self.name_row.set_text("")
        self.edit_group.add(self.name_row)

        # Port number
        port_adjustment = Gtk.Adjustment(
            value=80,
            lower=1,
            upper=65535,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        self.port_row = Adw.SpinRow()
        self.port_row.set_title(_("Port Number"))
        self.port_row.set_adjustment(port_adjustment)
        self.edit_group.add(self.port_row)

        # Protocol
        self.protocol_row = Adw.ComboRow()
        self.protocol_row.set_title(_("Protocol"))
        protocol_model = Gtk.StringList()
        protocol_model.append("tcp")
        protocol_model.append("udp")
        self.protocol_row.set_model(protocol_model)
        self.protocol_row.set_selected(0)  # Default to TCP
        self.edit_group.add(self.protocol_row)

        # Description
        self.description_row = Adw.EntryRow()
        self.description_row.set_title(_("Description"))
        self.description_row.set_text("")
        self.edit_group.add(self.description_row)

        # Access method
        self.access_method_row = Adw.ComboRow()
        self.access_method_row.set_title(_("Access Method"))
        access_model = Gtk.StringList()
        access_methods = ["", "http", "https", "ssh", "smb", "ftp", "rdp", "vnc"]
        for method in access_methods:
            access_model.append(method if method else "None")
        self.access_method_row.set_model(access_model)
        self.access_method_row.set_selected(0)
        self.edit_group.add(self.access_method_row)

        # Action buttons row
        buttons_row = Adw.ActionRow()
        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons_box.set_halign(Gtk.Align.END)

        # Cancel button
        cancel_button = Gtk.Button(label=_("Cancel"))
        cancel_button.connect("clicked", self.on_cancel_edit)
        buttons_box.append(cancel_button)

        # Save button
        save_button = Gtk.Button(label=_("Save"))
        save_button.add_css_class("suggested-action")
        save_button.connect("clicked", self.on_save_service)
        buttons_box.append(save_button)

        buttons_row.set_child(buttons_box)
        self.edit_group.add(buttons_row)

        # Validation message
        self.validation_label = Gtk.Label()
        self.validation_label.add_css_class("error")
        self.validation_label.set_visible(False)

        validation_row = Adw.ActionRow()
        validation_row.set_child(self.validation_label)
        self.edit_group.add(validation_row)

        # Add to UI
        self.custom_services_group.add(self.edit_group)

    def populate_edit_fields(self, service: ServiceInfo) -> None:
        """Populate edit form fields with service data."""
        self.name_row.set_text(service.name)
        self.port_row.set_value(service.port)
        self.protocol_row.set_selected(0 if service.protocol == "tcp" else 1)
        self.description_row.set_text(service.description or "")

        # Set access method
        access_methods = ["", "http", "https", "ssh", "smb", "ftp", "rdp", "vnc"]
        try:
            index = access_methods.index(service.access_method or "")
            self.access_method_row.set_selected(index)
        except ValueError:
            self.access_method_row.set_selected(0)

    def hide_edit_form(self) -> None:
        """Hide the edit form safely."""
        if self.edit_group and self.edit_group.get_parent():
            self.edit_group.get_parent().remove(self.edit_group)
        self.edit_group = None
        self.editing_service = None

    def validate_service_input(self) -> tuple[bool, str]:
        """Validate the service input."""
        name = self.name_row.get_text().strip()
        port = int(self.port_row.get_value())

        if not name:
            return False, _("Service name is required")

        if port < 1 or port > 65535:
            return False, _("Port must be between 1 and 65535")

        # Check for duplicate service (excluding the one being edited)
        existing_services = self.config_manager.get_custom_services()
        for service in existing_services:
            if (
                service.name == name
                and service.port == port
                and service != self.editing_service
            ):
                return False, _("Service") + f" '{name}' " + _(
                    "on port"
                ) + f" {port} " + _("already exists")

        return True, ""

    def on_add_service(self, button: Gtk.Button) -> None:
        """Handle add service button click."""
        if self.editing_service is not None:
            return  # Already editing

        self.editing_service = "new"  # Special marker for new service
        self.refresh_custom_services()

    def on_edit_service(self, service: ServiceInfo) -> None:
        """Handle edit service button click."""
        if self.editing_service is not None:
            return  # Already editing

        self.editing_service = service
        self.refresh_custom_services()

    def on_cancel_edit(self, button: Gtk.Button) -> None:
        """Handle cancel edit button click."""
        # Clear editing state first
        self.editing_service = None
        # Hide form and refresh
        self.hide_edit_form()
        self.refresh_custom_services()

    def on_save_service(self, button: Gtk.Button) -> None:
        """Handle save service button click."""
        is_valid, error_msg = self.validate_service_input()

        if not is_valid:
            self.validation_label.set_text(error_msg)
            self.validation_label.set_visible(True)
            return

        self.validation_label.set_visible(False)

        # Get form values
        name = self.name_row.get_text().strip()
        port = int(self.port_row.get_value())
        protocol = "tcp" if self.protocol_row.get_selected() == 0 else "udp"
        description = self.description_row.get_text().strip()

        # Get access method
        access_methods = ["", "http", "https", "ssh", "smb", "ftp", "rdp", "vnc"]
        selected_index = self.access_method_row.get_selected()
        access_method = access_methods[selected_index] if selected_index > 0 else None

        # Create new service
        new_service = ServiceInfo(
            name=name,
            port=port,
            protocol=protocol,
            description=description,
            access_method=access_method,
        )

        # Save service
        if self.editing_service == "new":
            self.config_manager.add_custom_service(new_service)
        else:
            # For updates, we need to remove the old service row since the key might change
            old_key = (
                self.editing_service.port,
                self.editing_service.protocol,
                self.editing_service.name,
            )
            if old_key in self.service_rows:
                old_row = self.service_rows[old_key]
                if old_row.get_parent() == self.custom_services_group:
                    self.custom_services_group.remove(old_row)
                del self.service_rows[old_key]

            # Update existing service using old port/protocol
            self.config_manager.update_custom_service(
                self.editing_service.port, self.editing_service.protocol, new_service
            )

        # Clear editing state first
        self.editing_service = None

        # Hide form and refresh
        self.hide_edit_form()
        self.refresh_custom_services()

    def on_delete_service(self, service: ServiceInfo) -> None:
        """Handle delete service button click."""
        dialog = Adw.MessageDialog(
            transient_for=self.parent_window,
            heading=_("Delete Custom Service"),
            body=_("Are you sure you want to delete")
            + f" '{service.name}' ({service.port}/{service.protocol})? "
            + _("This action cannot be undone."),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda d, r: self.on_delete_response(d, r, service))
        dialog.show()

    def on_delete_response(
        self, dialog: Adw.MessageDialog, response: str, service: ServiceInfo
    ) -> None:
        """Handle delete confirmation response."""
        if response == "delete":
            self.config_manager.remove_custom_service(service.port, service.protocol)
            self.refresh_custom_services()
        dialog.destroy()

    def on_clear_all_services(self, button: Gtk.Button) -> None:
        """Handle clear all services button."""
        custom_services = self.config_manager.get_custom_services()
        if not custom_services:
            return

        dialog = Adw.MessageDialog(
            transient_for=self.parent_window,
            heading=_("Clear All Custom Services"),
            body=_(
                "Are you sure you want to delete all custom services? This action cannot be undone."
            )
            + f" ({len(custom_services)})",
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.on_clear_all_response)
        dialog.show()

    def on_clear_all_response(self, dialog: Adw.MessageDialog, response: str) -> None:
        """Handle clear all confirmation response."""
        if response == "clear":
            self.config_manager.reset_custom_services()
            # Clear all tracked rows
            self.service_rows.clear()
            self.refresh_custom_services()
        dialog.destroy()

    def on_export_services(self, button: Gtk.Button) -> None:
        """Handle export services using native system dialog."""
        # Create file dialog for saving
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Export Custom Services"))
        dialog.set_initial_name("custom_services.json")

        # Create file filter for JSON files
        json_filter = Gtk.FileFilter()
        json_filter.set_name(_("JSON files"))
        json_filter.add_pattern("*.json")

        filter_list = Gio.ListStore()
        filter_list.append(json_filter)
        dialog.set_filters(filter_list)
        dialog.set_default_filter(json_filter)

        # Show save dialog
        dialog.save(self.parent_window, None, self._on_export_complete)

    def _on_export_complete(self, dialog: Gtk.FileDialog, result) -> None:
        """Handle export dialog completion."""
        try:
            file = dialog.save_finish(result)
            if file:
                file_path = file.get_path()
                if self.config_manager.export_custom_services(file_path):
                    self.show_message(
                        _("Export Successful"),
                        _("Custom services exported to ") + file_path,
                    )
                else:
                    self.show_message(
                        _("Export Failed"), _("Failed to export custom services")
                    )
        except Exception as e:
            # User cancelled or error occurred
            if "cancelled" not in str(e).lower():
                self.show_message(
                    _("Export Failed"), _("Failed to export custom services")
                )

    def on_import_services(self, button: Gtk.Button) -> None:
        """Handle import services using native system dialog."""
        # Create file dialog for opening
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Import Custom Services"))

        # Create file filter for JSON files
        json_filter = Gtk.FileFilter()
        json_filter.set_name(_("JSON files"))
        json_filter.add_pattern("*.json")

        filter_list = Gio.ListStore()
        filter_list.append(json_filter)
        dialog.set_filters(filter_list)
        dialog.set_default_filter(json_filter)

        # Show open dialog
        dialog.open(self.parent_window, None, self._on_import_complete)

    def _on_import_complete(self, dialog: Gtk.FileDialog, result) -> None:
        """Handle import dialog completion."""
        try:
            file = dialog.open_finish(result)
            if file:
                file_path = file.get_path()
                success, count = self.config_manager.import_custom_services(file_path)
                if success:
                    self.show_message(
                        _("Import Successful"),
                        _("Imported ") + str(count) + _(" custom services"),
                    )
                    # Clear tracked rows and refresh
                    self.service_rows.clear()
                    self.refresh_custom_services()
                else:
                    self.show_message(
                        _("Import Failed"), _("Failed to import custom services")
                    )
        except Exception as e:
            # User cancelled or error occurred
            if "cancelled" not in str(e).lower():
                self.show_message(
                    _("Import Failed"), _("Failed to import custom services")
                )

    def show_message(self, title: str, message: str) -> None:
        """Show info message dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self.parent_window, heading=title, body=message
        )
        dialog.add_response("ok", _("OK"))
        dialog.show()

    # Detection settings callback methods
    def on_ping_timeout_changed(self, spin_row, *args) -> None:
        """Handle ping timeout setting change."""
        new_value = spin_row.get_value()
        self.config_manager.config.ping_timeout = new_value
        self.config_manager.save_config()

    def on_ping_attempts_changed(self, spin_row, *args) -> None:
        """Handle ping attempts setting change."""
        new_value = int(spin_row.get_value())
        self.config_manager.config.ping_attempts = new_value
        self.config_manager.save_config()

    def on_hostname_timeout_changed(self, spin_row, *args) -> None:
        """Handle hostname timeout setting change."""
        new_value = spin_row.get_value()
        self.config_manager.config.hostname_timeout = new_value
        self.config_manager.save_config()

    def on_discovery_threads_changed(self, spin_row, *args) -> None:
        """Handle discovery threads setting change."""
        new_value = int(spin_row.get_value())
        self.config_manager.config.discovery_threads = new_value
        self.config_manager.save_config()

    def on_scan_timeout_changed(self, spin_row, *args) -> None:
        """Handle scan timeout setting change."""
        new_value = spin_row.get_value()
        self.config_manager.config.scan_timeout = new_value
        self.config_manager.save_config()

    def on_scan_threads_changed(self, spin_row, *args) -> None:
        """Handle scan threads setting change."""
        new_value = int(spin_row.get_value())
        self.config_manager.config.scan_threads = new_value
        self.config_manager.save_config()
