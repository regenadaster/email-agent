"""Compatibility bridge for the repository's existing import path.

New code should import ``MacOSCalendarService`` from
``email_agent.services.macos_calendar``.  The current ``agent_server.py`` still
imports ``book_calendar_event`` from this module, so this re-export keeps that
code working while the service layer is migrated incrementally.
"""

from email_agent.services.macos_calendar import book_calendar_event

__all__ = ["book_calendar_event"]
