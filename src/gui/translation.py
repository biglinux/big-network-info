from pathlib import Path
import gettext
import locale

# Set locale from environment
locale.setlocale(locale.LC_ALL, "")
# Define locale directory relative to project root
LOCALE_DIR = Path(__file__).parent.parent / "locale"

# Bind text domain
DOMAIN = "big-network-info"
gettext.bindtextdomain(DOMAIN, str(LOCALE_DIR))
gettext.textdomain(DOMAIN)

# Alias for gettext
_ = gettext.gettext
