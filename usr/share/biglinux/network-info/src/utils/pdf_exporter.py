"""
PDF export utility for network scan results and diagnostics.
Generates professional PDF reports with scan data.
"""

from datetime import datetime
from typing import List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
)
from reportlab.lib.enums import TA_CENTER

from ..core.scanner import ScanResult
from ..core.network_diagnostics import DiagnosticStep, DiagnosticStatus
from ..gui.translation import _


class PDFExporter:
    """Generate professional PDF reports from scan results."""

    def __init__(self):
        """Initialize the PDF exporter."""
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()

    def setup_custom_styles(self):
        """Setup custom paragraph styles for the PDF."""
        # Modern color palette - store as instance variables
        self.primary_color = colors.HexColor("#007AFF")  # A vibrant blue
        self.secondary_color = colors.HexColor(
            "#34C759"
        )  # A friendly green for success
        self.warning_color = colors.HexColor("#FF9500")  # A clear orange for warnings
        self.error_color = colors.HexColor("#FF3B30")  # A distinct red for errors

        self.dark_text = colors.HexColor("#1D1D1F")  # Near black for body text
        self.medium_text = colors.HexColor(
            "#6E6E73"
        )  # Grey for subtitles/secondary info
        self.light_text = colors.HexColor(
            "#F2F2F7"
        )  # Light grey/white for dark backgrounds

        self.light_bg = colors.HexColor(
            "#F8F9FA"
        )  # Very light grey for backgrounds/cards
        self.card_bg = colors.HexColor("#FFFFFF")  # White for host cards
        self.table_header_bg = colors.HexColor(
            "#E5E5EA"
        )  # Slightly darker grey for table headers
        self.gateway_bg = colors.HexColor("#E3F2FD")  # Light blue for gateways
        self.service_bg = colors.HexColor("#F1F8E9")  # Light green for services
        self.client_bg = colors.HexColor("#FFF3E0")  # Light orange for clients

        # Enhanced border colors
        self.border_color = colors.HexColor("#D1D1D6")
        self.accent_border = colors.HexColor("#007AFF")

        # Title style - modern and bold
        self.styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=self.styles["Title"],
                fontSize=28,
                spaceAfter=0.3 * inch,
                alignment=TA_CENTER,
                textColor=self.primary_color,
                fontName="Helvetica-Bold",
            )
        )

        # Subtitle style - clean and professional
        self.styles.add(
            ParagraphStyle(
                name="CustomSubtitle",
                parent=self.styles["Normal"],
                fontSize=13,
                spaceAfter=0.4 * inch,
                alignment=TA_CENTER,
                textColor=self.medium_text,
                fontName="Helvetica",
                leading=18,
            )
        )

        # Section header style with enhanced background
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=20,
                spaceBefore=0.5 * inch,
                spaceAfter=0.3 * inch,
                textColor=self.primary_color,
                fontName="Helvetica-Bold",
                leftIndent=12,
                rightIndent=12,
                borderPadding=(8, 12, 8, 12),
                backColor=self.light_bg,
                borderWidth=1,
                borderColor=self.border_color,
            )
        )

        # Category header with color coding
        self.styles.add(
            ParagraphStyle(
                name="CategoryHeader",
                parent=self.styles["Heading3"],
                fontSize=16,
                spaceBefore=0.4 * inch,
                spaceAfter=0.2 * inch,
                textColor=self.dark_text,
                fontName="Helvetica-Bold",
                leftIndent=8,
                borderPadding=(6, 8, 6, 8),
                backColor=self.light_bg,
            )
        )

        # Gateway category header
        self.styles.add(
            ParagraphStyle(
                name="GatewayHeader",
                parent=self.styles["CategoryHeader"],
                textColor=self.primary_color,
                backColor=self.gateway_bg,
                borderWidth=1,
                borderColor=self.primary_color,
            )
        )

        # Service devices category header
        self.styles.add(
            ParagraphStyle(
                name="ServiceHeader",
                parent=self.styles["CategoryHeader"],
                textColor=self.secondary_color,
                backColor=self.service_bg,
                borderWidth=1,
                borderColor=self.secondary_color,
            )
        )

        # Client devices category header
        self.styles.add(
            ParagraphStyle(
                name="ClientHeader",
                parent=self.styles["CategoryHeader"],
                textColor=self.warning_color,
                backColor=self.client_bg,
                borderWidth=1,
                borderColor=self.warning_color,
            )
        )

        # Enhanced info paragraph style
        self.styles.add(
            ParagraphStyle(
                name="InfoText",
                parent=self.styles["Normal"],
                fontSize=11,
                spaceAfter=0.08 * inch,
                textColor=self.dark_text,
                fontName="Helvetica",
                leading=15,
                leftIndent=4,
            )
        )

        # Host title style for device names
        self.styles.add(
            ParagraphStyle(
                name="HostTitle",
                parent=self.styles["Normal"],
                fontSize=13,
                spaceAfter=0.1 * inch,
                textColor=self.primary_color,
                fontName="Helvetica-Bold",
                leading=16,
            )
        )

        # Service list style
        self.styles.add(
            ParagraphStyle(
                name="ServiceText",
                parent=self.styles["Normal"],
                fontSize=10,
                textColor=self.dark_text,
                fontName="Helvetica",
                leading=13,
                leftIndent=8,
                bulletIndent=16,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="SmallInfoText",
                parent=self.styles["InfoText"],
                fontSize=9,
                textColor=self.medium_text,
                leftIndent=8,
            )
        )

        # Summary box style
        self.styles.add(
            ParagraphStyle(
                name="SummaryText",
                parent=self.styles["Normal"],
                fontSize=12,
                textColor=self.dark_text,
                fontName="Helvetica",
                leading=18,
                leftIndent=12,
                rightIndent=12,
                spaceBefore=0.1 * inch,
                spaceAfter=0.2 * inch,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="FooterText",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=self.medium_text,
                alignment=TA_CENTER,
                fontName="Helvetica-Oblique",
            )
        )

        # Enhanced status styles with background and bottom margin
        self.styles.add(
            ParagraphStyle(
                name="StatusPassed",
                parent=self.styles["Normal"],
                textColor=colors.white,
                fontName="Helvetica-Bold",
                fontSize=10,
                backColor=self.secondary_color,
                borderPadding=(3, 6, 3, 6),
                spaceAfter=12,  # 12px bottom margin
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="StatusFailed",
                parent=self.styles["Normal"],
                textColor=colors.white,
                fontName="Helvetica-Bold",
                fontSize=10,
                backColor=self.error_color,
                borderPadding=(3, 6, 3, 6),
                spaceAfter=12,  # 12px bottom margin
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="StatusWarning",
                parent=self.styles["Normal"],
                textColor=colors.white,
                fontName="Helvetica-Bold",
                fontSize=10,
                backColor=self.warning_color,
                borderPadding=(3, 6, 3, 6),
                spaceAfter=12,  # 12px bottom margin
            )
        )

    def export_to_pdf(
        self,
        results: List[ScanResult],
        filename: Optional[str] = None,
        network_range: Optional[str] = None,
    ) -> str:
        """
        Export scan results to PDF file.

        Args:
            results: List of scan results
            filename: Optional filename, generates timestamp-based name if None
            network_range: Network range that was scanned (e.g., "192.168.1.0/24")

        Returns:
            Path to the generated PDF file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = _("network_scan_report") + f"_{timestamp}.pdf"

        if not filename.endswith(".pdf"):
            filename += ".pdf"

        doc = SimpleDocTemplate(
            filename,
            pagesize=A4,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        story = []
        self._add_header(story, results, _("Network Scan Report"))
        self._add_executive_summary(story, results, network_range)
        self._add_detailed_results(story, results)
        self._add_network_statistics(story, results)
        self._add_footer(story)

        doc.build(story)
        return filename

    def _add_header(
        self, story: list, results: Optional[List[ScanResult]], report_title: str
    ):
        """Add PDF header with title and scan info."""
        title = Paragraph(report_title, self.styles["CustomTitle"])
        story.append(title)

        scan_time = datetime.now().strftime("%B %d, %Y at %H:%M")
        subtitle_text = _("Generated on") + f" {scan_time}"
        if results is not None:  # Specific to scan report
            host_count = len(results)
            service_count = sum(len(result.services) for result in results)
            subtitle_text += (
                "<br/>"
                + f"<b>{host_count}</b> "
                + _("devices discovered with")
                + f" <b>{service_count}</b> "
                + _("total services")
            )

        subtitle = Paragraph(subtitle_text, self.styles["CustomSubtitle"])
        story.append(subtitle)
        # story.append(Spacer(1, 0.1 * inch)) # Reduced spacer after subtitle

    def _add_executive_summary(
        self,
        story: list,
        results: List[ScanResult],
        network_range: Optional[str] = None,
    ):
        """Add executive summary section with modern layout."""
        story.append(Paragraph(_("📊 Scan Overview"), self.styles["SectionHeader"]))

        range_display = network_range or _("Not specified")
        active_hosts = len([r for r in results if r.is_alive])
        hosts_with_services = len([r for r in results if r.services])
        total_services = sum(len(r.services) for r in results)
        gateways = [r for r in results if self._is_gateway(r)]

        # Create a summary table for better visual presentation
        summary_data = [
            [
                Paragraph(
                    "<b>🌐 " + _("Network Range") + "</b>", self.styles["InfoText"]
                ),
                Paragraph(f"{range_display}", self.styles["InfoText"]),
            ],
            [
                Paragraph(
                    "<b>💻 " + _("Active Devices") + "</b>", self.styles["InfoText"]
                ),
                Paragraph(
                    "<font color='#34C759'><b>" + str(active_hosts) + "</b></font>",
                    self.styles["InfoText"],
                ),
            ],
            [
                Paragraph(
                    "<b>⚙️ " + _("Devices with Services") + "</b>",
                    self.styles["InfoText"],
                ),
                Paragraph(
                    "<font color='#007AFF'><b>"
                    + str(hosts_with_services)
                    + "</b></font>",
                    self.styles["InfoText"],
                ),
            ],
            [
                Paragraph(
                    "<b>🔧 " + _("Total Services") + "</b>", self.styles["InfoText"]
                ),
                Paragraph(
                    "<font color='#FF9500'><b>" + str(total_services) + "</b></font>",
                    self.styles["InfoText"],
                ),
            ],
            [
                Paragraph(
                    "<b>🏠 " + _("Network Gateways") + "</b>", self.styles["InfoText"]
                ),
                Paragraph(
                    "<font color='#007AFF'><b>" + str(len(gateways)) + "</b></font>",
                    self.styles["InfoText"],
                ),
            ],
        ]

        summary_table = Table(summary_data, colWidths=[3.5 * inch, 2.5 * inch])
        summary_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), self.card_bg),
                ("BOX", (0, 0), (-1, -1), 1, self.border_color),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, self.border_color),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [self.card_bg, self.light_bg]),
            ])
        )

        story.append(summary_table)
        story.append(Spacer(1, 0.3 * inch))

    def _add_detailed_results(self, story: list, results: List[ScanResult]):
        """Add detailed scan results."""
        story.append(
            Paragraph(_("🔍 Detailed Device Information"), self.styles["SectionHeader"])
        )

        sorted_results = self._sort_results(results)
        gateways = [r for r in sorted_results if self._is_gateway(r)]
        devices_with_services = [
            r for r in sorted_results if not self._is_gateway(r) and r.services
        ]
        clients = [
            r for r in sorted_results if not self._is_gateway(r) and not r.services
        ]

        if gateways:
            self._add_host_category(
                story, _("🏠 Network Infrastructure"), gateways, "gateway"
            )
        if devices_with_services:
            self._add_host_category(
                story, _("⚙️ Devices & Services"), devices_with_services, "service"
            )
        if clients:
            self._add_host_category(
                story, _("💻 Other Active Clients"), clients, "client"
            )

    def _add_host_category(
        self,
        story: list,
        title: str,
        hosts: List[ScanResult],
        category_type: str = "default",
    ):
        """Add a category of hosts to the PDF with enhanced visual design."""
        # Choose the appropriate header style based on category
        header_style = "CategoryHeader"
        if category_type == "gateway":
            header_style = "GatewayHeader"
        elif category_type == "service":
            header_style = "ServiceHeader"
        elif category_type == "client":
            header_style = "ClientHeader"

        story.append(
            Paragraph(
                title + f" ({len(hosts)} " + _("devices") + ")",
                self.styles[header_style],
            )
        )

        for i, host in enumerate(hosts):
            # Determine background color based on category
            if category_type == "gateway":
                card_bg = self.gateway_bg
                border_color = self.primary_color
            elif category_type == "service":
                card_bg = self.service_bg
                border_color = self.secondary_color
            elif category_type == "client":
                card_bg = self.client_bg
                border_color = self.warning_color
            else:
                card_bg = self.card_bg
                border_color = self.border_color

            response_time_text = _("N/A")
            if host.response_time and host.response_time > 0:
                response_time_text = f"{host.response_time:.1f}ms"
            elif (
                hasattr(host, "response_time") and host.response_time == 0
            ):  # Assuming 0 means very fast
                response_time_text = _("<1ms")

            # Create host title with IP address
            host_title = f"🖥️ {host.hostname or host.ip}"
            if host.hostname and host.hostname != host.ip:
                host_title += f" ({host.ip})"

            host_info_paras = [
                Paragraph(host_title, self.styles["HostTitle"]),
                Paragraph(
                    f"<b>📍 {_('IP Address:')}</b> {host.ip}", self.styles["InfoText"]
                ),
                Paragraph(
                    f"<b>🔗 {_('MAC Address:')}</b> {host.mac or _('Not detected')}",
                    self.styles["InfoText"],
                ),
                Paragraph(
                    f"<b>🏢 {_('Vendor:')}</b> {host.vendor or _('Unknown')}",
                    self.styles["InfoText"],
                ),
                Paragraph(
                    f"<b>⚡ {_('Response Time:')}</b> {response_time_text}",
                    self.styles["InfoText"],
                ),
            ]

            services_paras = []
            if host.services:
                services_paras.append(
                    Paragraph(
                        f"<b>🔧 {_('Services Detected:')}</b>", self.styles["InfoText"]
                    )
                )
                for service in sorted(host.services, key=lambda s: s.port):
                    desc = service.description
                    if len(desc) > 40:
                        desc = desc[:37] + "..."

                    # Color code common services
                    service_color = "#6E6E73"  # default grey
                    if service.name.lower() in [
                        "http",
                        "https",
                        "ssh",
                        "ftp",
                        "telnet",
                    ]:
                        service_color = "#007AFF"  # blue for common services
                    elif service.name.lower() in ["smtp", "pop3", "imap"]:
                        service_color = "#34C759"  # green for mail services

                    services_paras.append(
                        Paragraph(
                            f"• <font color='{service_color}'><b>{service.name}</b></font> "
                            f"({service.port}/{service.protocol.upper()}): {desc}",
                            self.styles["ServiceText"],
                        )
                    )
            else:
                services_paras.append(
                    Paragraph(
                        "ℹ️ " + _("No services detected."), self.styles["SmallInfoText"]
                    )
                )

            # Create a table for layout: one row, two columns with card appearance
            data = [[host_info_paras, services_paras]]
            table = Table(data, colWidths=[3.2 * inch, 3.3 * inch])
            table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), card_bg),
                    ("BOX", (0, 0), (-1, -1), 1.5, border_color),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ])
            )
            story.append(table)
            story.append(Spacer(1, 0.25 * inch))  # Space after each host entry

    def _add_network_statistics(self, story: list, results: List[ScanResult]):
        """Add network statistics with enhanced visual presentation."""
        story.append(PageBreak())
        story.append(Paragraph(_("📈 Network Analytics"), self.styles["SectionHeader"]))

        service_counts = {}
        for result in results:
            for service in result.services:
                service_name = service.name
                service_counts[service_name] = service_counts.get(service_name, 0) + 1

        if service_counts:
            story.append(
                Paragraph(_("🔧 Most Common Services"), self.styles["ServiceHeader"])
            )
            sorted_services = sorted(
                service_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]

            service_data = [
                [
                    Paragraph(f"<b>🔧 {_('Service')}</b>", self.styles["InfoText"]),
                    Paragraph(f"<b>📊 {_('Count')}</b>", self.styles["InfoText"]),
                    Paragraph(f"<b>📈 {_('Percentage')}</b>", self.styles["InfoText"]),
                ]
            ]
            total_detected_services = sum(
                service_counts.values()
            )  # Use this for percentage calculation

            for service, count in sorted_services:
                percentage = (
                    (count / total_detected_services) * 100
                    if total_detected_services > 0
                    else 0
                )

                # Color code based on percentage
                if percentage >= 20:
                    count_color = "#FF3B30"  # red for high usage
                elif percentage >= 10:
                    count_color = "#FF9500"  # orange for medium usage
                else:
                    count_color = "#34C759"  # green for low usage

                service_data.append([
                    Paragraph(f"<b>{service}</b>", self.styles["InfoText"]),
                    Paragraph(
                        f"<font color='{count_color}'><b>{count}</b></font>",
                        self.styles["InfoText"],
                    ),
                    Paragraph(
                        f"<font color='{count_color}'><b>{percentage:.1f}%</b></font>",
                        self.styles["InfoText"],
                    ),
                ])

            services_table = Table(
                service_data, colWidths=[3 * inch, 1.5 * inch, 2 * inch]
            )
            services_table.setStyle(
                TableStyle([
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        self.primary_color,
                    ),  # Header with primary color
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                    ("TOPPADDING", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                    ("TOPPADDING", (0, 1), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, self.border_color),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [self.card_bg, self.light_bg]),
                ])
            )
            story.append(services_table)

    def _add_footer(self, story: list):
        """Adds an enhanced footer to the story."""
        story.append(Spacer(1, 0.4 * inch))

        # Add a separator line
        separator_table = Table([[""]], colWidths=[6.5 * inch])
        separator_table.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, -1), 2, self.primary_color),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        story.append(separator_table)
        story.append(Spacer(1, 0.2 * inch))

        footer_text = (
            "📋 "
            + _("Report generated by")
            + " <b>Big Network Info</b> • "
            + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        story.append(Paragraph(footer_text, self.styles["FooterText"]))

    def _is_gateway(self, result: ScanResult) -> bool:
        """Check if a result represents a gateway/router."""
        is_gateway_ip = result.ip.endswith((".1", ".254"))  # .255 is broadcast
        hostname_lower = result.hostname.lower()
        is_gateway_hostname = any(
            term in hostname_lower
            for term in ["gateway", "router", "gw", "rt", "firewall", "fw"]
        )
        has_web_interface = any(
            service.port in [80, 443] for service in result.services
        )
        return is_gateway_ip or (is_gateway_hostname and has_web_interface)

    def _sort_results(self, results: List[ScanResult]) -> List[ScanResult]:
        """Sort results: gateways, then devices with services, then clients."""
        gateways = []
        devices_with_services = []
        clients_without_services = []

        for result in results:
            if self._is_gateway(result):
                gateways.append(result)
            elif result.services:
                devices_with_services.append(result)
            else:
                clients_without_services.append(result)

        gateways.sort(key=lambda r: self._ip_to_int(r.ip))
        devices_with_services.sort(
            key=lambda r: (-len(r.services), self._ip_to_int(r.ip))
        )
        clients_without_services.sort(key=lambda r: self._ip_to_int(r.ip))
        return gateways + devices_with_services + clients_without_services

    def _ip_to_int(self, ip: str) -> int:
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
            return 0  # Fallback for invalid IPs

    def export_diagnostics_to_pdf(
        self,
        steps: List[DiagnosticStep],
        filename: Optional[str] = None,
    ) -> str:
        """
        Export diagnostics results to PDF file.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = _("network_diagnostics_report") + f"_{timestamp}.pdf"

        if not filename.endswith(".pdf"):
            filename += ".pdf"

        doc = SimpleDocTemplate(
            filename,
            pagesize=A4,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )
        story = []

        self._add_header(story, None, _("Network Diagnostics Report"))
        self._add_diagnostics_summary(story, steps)
        self._add_diagnostics_details(story, steps)
        self._add_diagnostics_recommendations(story, steps)
        self._add_footer(story)

        doc.build(story)
        return filename

    def _add_diagnostics_summary(self, story: list, steps: List[DiagnosticStep]):
        """Add diagnostics summary section."""
        story.append(Paragraph(_("Diagnostics Overview"), self.styles["SectionHeader"]))

        passed = sum(1 for step in steps if step.status == DiagnosticStatus.PASSED)
        failed = sum(1 for step in steps if step.status == DiagnosticStatus.FAILED)
        warnings = sum(1 for step in steps if step.status == DiagnosticStatus.WARNING)

        summary_content = (
            "<b>" + _("Passed Tests") + "</b>: " + str(passed) + "<br/>"
            "<b>" + _("Failed Tests") + "</b>: " + str(failed) + "<br/>"
            "<b>" + _("Warnings") + "</b>: " + str(warnings) + "<br/>"
            "<b>" + _("Total Tests Performed") + "</b>: " + str(len(steps))
        )
        story.append(Paragraph(summary_content, self.styles["InfoText"]))
        # story.append(Spacer(1, 0.2 * inch))

    def _add_diagnostics_details(self, story: list, steps: List[DiagnosticStep]):
        """Add detailed diagnostics results."""
        story.append(
            Paragraph(_("Detailed Test Results"), self.styles["SectionHeader"])
        )

        for i, step in enumerate(steps):
            story.append(
                Paragraph(f"{i + 1}. {step.name}", self.styles["CategoryHeader"])
            )

            status_style = self.styles["Normal"]
            status_text_raw = _("Unknown")
            if step.status == DiagnosticStatus.PASSED:
                status_style = self.styles["StatusPassed"]
                status_text_raw = _("PASSED")
            elif step.status == DiagnosticStatus.FAILED:
                status_style = self.styles["StatusFailed"]
                status_text_raw = _("FAILED")
            elif step.status == DiagnosticStatus.WARNING:
                status_style = self.styles["StatusWarning"]
                status_text_raw = _("WARNING")

            status_text = f"{status_text_raw}"
            story.append(Paragraph(status_text, status_style))

            if step.description:
                story.append(
                    Paragraph(
                        _("Test:") + " " + step.description,
                        self.styles["InfoText"],
                    )
                )
            if step.details:
                story.append(
                    Paragraph(
                        _("Details:") + " " + str(step.details),
                        self.styles["SmallInfoText"],
                    )
                )
            if step.duration_ms > 0:
                story.append(
                    Paragraph(
                        _("Duration:") + f" {step.duration_ms}ms",
                        self.styles["SmallInfoText"],
                    )
                )

            if step.status == DiagnosticStatus.FAILED and step.troubleshooting_tip:
                story.append(
                    Paragraph(
                        _("Suggestion:") + " " + step.troubleshooting_tip,
                        self.styles["SmallInfoText"],
                    )
                )
            story.append(Spacer(1, 0.15 * inch))

    def _add_diagnostics_recommendations(
        self, story: list, steps: List[DiagnosticStep]
    ):
        """Add recommendations based on diagnostics results."""
        failed_or_warning_steps = [
            step
            for step in steps
            if step.status in [DiagnosticStatus.FAILED, DiagnosticStatus.WARNING]
        ]

        if not failed_or_warning_steps:
            story.append(
                Paragraph(_("Overall Assessment"), self.styles["SectionHeader"])
            )
            story.append(
                Paragraph(
                    _(
                        "✓ All network diagnostics passed! Your network connectivity appears healthy."
                    ),
                    self.styles["StatusPassed"],
                )
            )
            return

        story.append(
            Paragraph(_("Recommendations & Next Steps"), self.styles["SectionHeader"])
        )
        story.append(
            Paragraph(
                _(
                    "The following items may require attention based on the diagnostics:"
                ),
                self.styles["InfoText"],
            )
        )

        for i, step in enumerate(failed_or_warning_steps, 1):
            prefix = "✗" if step.status == DiagnosticStatus.FAILED else "⚠"
            recommendation = (
                f"{i}. <b>{step.name} ({prefix} {step.status.value.upper()})</b>: "
            )
            if step.troubleshooting_tip:
                recommendation += step.troubleshooting_tip
            elif step.details:
                recommendation += _("Review details") + f": {step.details}"
            else:
                recommendation += _("Review this test step for potential issues.")

            style = (
                self.styles["StatusFailed"]
                if step.status == DiagnosticStatus.FAILED
                else self.styles["StatusWarning"]
            )
            story.append(Paragraph(recommendation, style))
            story.append(Spacer(1, 0.05 * inch))
