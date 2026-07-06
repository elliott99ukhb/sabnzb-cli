"""sabnzb-cli — a lightweight command-line dashboard for monitoring SABnzbd."""

import warnings

# macOS system Python ships an old LibreSSL that makes urllib3 emit a
# NotOpenSSLWarning on every run. It's harmless here and only clutters output.
# Filter by message so we don't have to import urllib3 first (importing it to
# get the warning class is what triggers the warning in the first place).
warnings.filterwarnings("ignore", message=r"urllib3 v2 only supports OpenSSL.*")

__version__ = "0.2.0"
