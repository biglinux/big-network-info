"""
Translation utility module to ensure consistent translations throughout the application
"""

import gettext

gettext.textdomain("big-network-info")
_ = gettext.gettext
