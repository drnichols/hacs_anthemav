# Anthem A/V Receivers (HACS)

A Home Assistant custom integration for Anthem A/V receivers and processors, installable through [HACS](https://hacs.xyz).

It is a packaged copy of the core [`anthemav`](https://www.home-assistant.io/integrations/anthemav) integration, using the domain `hacs_anthemav` so it can run **alongside** the official integration without conflict.

## Features

- One `media_player` entity per zone the receiver reports
- Power on/off, volume, mute and source selection
- Current input name and input format (shown as the media title and app name)
- Local push: the receiver sends updates, nothing is polled
- Entities show as unavailable while the receiver is disconnected, and recover automatically when it comes back
- Zone 1 is the receiver device. Zones 2 and above appear as child devices of it.

## Requirements

Home Assistant **2026.2.3** or newer (the version this integration has been tested against).

## Installation

### HACS (custom repository)

1. In Home Assistant, open **HACS**.
2. Open the menu (top right) and choose **Custom repositories**.
3. Add `https://github.com/drnichols/hacs_anthemav` with category **Integration**.
4. Find **Anthem A/V Receivers (HACS)** in HACS and click **Download**.
5. Restart Home Assistant.

### Manual

Copy `custom_components/hacs_anthemav` into the `custom_components` folder of your Home Assistant configuration, then restart Home Assistant.

## Setup

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **Anthem A/V Receivers (HACS)**.
3. Enter the receiver's IP address or hostname. The port defaults to `14999`.

The receiver must be powered on during setup so its MAC address and model can be read. The MAC address is used as the unique ID, so the same receiver cannot be added twice.

## Now playing from another media player

Many inputs (e.g. an Apple TV) only tell the receiver the input name. To show real now-playing details and cover art, open the integration's **Configure** dialog and pick a media player for each input, such as `media_player.lounge` for `ATV`. While that input is selected, the receiver entity mirrors the title, artist, album, duration, position and artwork from that player. If the player is off, idle or unavailable, the entity shows the input name as before. This is display only; playback controls stay on the source player.

## Changing the receiver's address

If the receiver's IP address changes, open the integration under **Settings → Devices & services**, choose the menu (⋮) and **Reconfigure**. The new address must belong to the same receiver (matched by MAC address). Adding the same receiver again at a new address also updates the stored address.

## Troubleshooting

- **Failed to connect**: check the host and port, and that the receiver is on the network and its IP control is enabled.
- **Failed to retrieve MAC address**: make sure the receiver is turned on, then try again.
- **Using both integrations**: some receivers accept only one network connection at a time. Don't add the same receiver to both this integration and the official one.
- Enable debug logging by adding `custom_components.hacs_anthemav: debug` under `logger:` in `configuration.yaml`.

## Credits and licence

Based on the Home Assistant core `anthemav` integration and the [`anthemav`](https://pypi.org/project/anthemav/) Python library. Licensed under the Apache License 2.0, see [LICENSE](LICENSE).
