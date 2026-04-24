"""
Translation utility module to ensure consistent translations throughout the application
"""

import gettext
import os
from pathlib import Path

DOMAIN = "big-network-info"


def _find_locale_dir() -> str:
    """Locate the directory containing compiled .mo translation files.

    Looks in this order:
      1. Package-local `locale/` (editable install / source run).
      2. System prefix from `$PREFIX/share/locale` if `PREFIX` is set.
      3. `/usr/share/locale` (standard install target).
    """
    package_locale = Path(__file__).resolve().parent.parent / "locale"
    if package_locale.is_dir():
        return str(package_locale)

    prefix = os.environ.get("PREFIX")
    if prefix:
        candidate = Path(prefix) / "share" / "locale"
        if candidate.is_dir():
            return str(candidate)

    return "/usr/share/locale"


_locale_dir = _find_locale_dir()
gettext.bindtextdomain(DOMAIN, _locale_dir)
try:
    gettext.bind_textdomain_codeset(DOMAIN, "UTF-8")
except AttributeError:
    pass
gettext.textdomain(DOMAIN)
_ = gettext.gettext
