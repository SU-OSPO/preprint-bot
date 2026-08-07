"""Runtime settings for preprint sources (env-overridable).

Self-contained so the package has no dependency on preprint_bot.config.
"""
import os

# Sent as the User-Agent header on outbound requests to preprint servers.
# Override with the PREPRINT_SOURCES_USER_AGENT environment variable.
USER_AGENT = os.environ.get("PREPRINT_SOURCES_USER_AGENT", "PreprintBot/1.0")
