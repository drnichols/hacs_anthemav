"""AVR protocol wrapper that reports connection changes to Home Assistant."""

from typing import override

from anthemav.protocol import AVR


class NotifyingAVR(AVR):
    """AVR protocol that also fires the update callback on connect/disconnect.

    The library only calls the update callback when the receiver sends data, so
    a dropped connection would otherwise go unnoticed until the next message.
    """

    @property
    def connected(self) -> bool:
        """Return True while there is a live connection to the receiver."""
        return self.transport is not None

    def _notify(self, message: str) -> None:
        if self._update_callback:
            self._loop.call_soon(self._update_callback, message)

    @override
    def connection_made(self, transport) -> None:
        super().connection_made(transport)
        self._notify("connection_made")

    @override
    def connection_lost(self, exc) -> None:
        super().connection_lost(exc)
        self._notify("connection_lost")
