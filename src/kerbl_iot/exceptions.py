"""Exceptions raised by the Kerbl IoT client."""


class KerblError(Exception):
    """Base exception for Kerbl IoT client errors."""


class KerblAuthenticationError(KerblError):
    """Authentication failed or the stored session could not be refreshed."""


class KerblConnectionError(KerblError):
    """The Kerbl IoT service could not be reached."""


class KerblProtocolError(KerblError):
    """The Kerbl IoT service returned an unexpected response."""


class KerblStateError(KerblError):
    """A command cannot safely be applied to the reported device state."""
