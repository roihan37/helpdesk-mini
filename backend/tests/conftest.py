import os

# The local M0 environment predates this required M2 setting. Tests make the
# local-only cookie policy explicit without weakening production configuration.
os.environ.setdefault("REFRESH_COOKIE_SECURE", "false")
