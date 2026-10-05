"""AVR protocol wrapper that reports connection changes to Home Assistant."""

from typing import override

from anthemav.protocol import AVR, MODEL_X20


class NotifyingAVR(AVR):
    """AVR protocol that also fires the update callback on connect/disconnect.

    The library only calls the update callback when the receiver sends data, so
    a dropped connection would otherwise go unnoticed until the next message.
    """

    @property
    def connected(self) -> bool:
        """Return True while there is a live connection to the receiver."""
        return self.transport is not None

    @property
    def has_x20_settings(self) -> bool:
        """Return True for x20 receivers, the only series the library can configure.

        Front panel brightness and standby IP control are only queried and
        driven by the library on x20 models. The x40 equivalents (e.g. GCFPB)
        are not wired up in its brightness property, so they are not offered.
        """
        return self._model_series == MODEL_X20

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
