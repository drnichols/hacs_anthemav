"""Tests for mirroring now-playing details from another media player."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_anthemav.const import (
    CONF_APP_NAME_FORMAT,
    CONF_SOURCE_PLAYERS,
    DOMAIN,
)
from custom_components.hacs_anthemav.media_player import render_app_name

from .test_init import MAC, entity_id, mock_connection

SOURCE = "media_player.lounge"


async def setup_mapped(hass: HomeAssistant, avr, mapping=None, extra_options=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        title="Anthem AV (HACS)",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 14999,
            CONF_MAC: MAC,
            CONF_MODEL: "MRX 540",
        },
        options={CONF_SOURCE_PLAYERS: mapping or {"ATV": SOURCE}, **(extra_options or {})},
    )
    entry.add_to_hass(hass)
    with patch("anthemav.Connection.create", AsyncMock(return_value=avr)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def playing(**extra):
    return {
        "media_title": "Severance",
        "media_artist": "Apple TV+",
        "media_album_name": "Season 2",
        "media_duration": 3000,
        **extra,
    }


async def test_mirrors_mapped_source(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.zones[1].input_name = "ATV"
    hass.states.async_set(SOURCE, "playing", playing())
    await setup_mapped(hass, avr)

    state = hass.states.get(entity_id(hass))
    assert state.state == "on"
    assert state.attributes["media_title"] == "Severance"
    assert state.attributes["media_artist"] == "Apple TV+"
    assert state.attributes["media_album_name"] == "Season 2"
    assert state.attributes["media_duration"] == 3000
    assert state.attributes["source"] == "ATV"


async def test_follows_mapped_player_updates(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.zones[1].input_name = "ATV"
    hass.states.async_set(SOURCE, "playing", playing())
    await setup_mapped(hass, avr)

    hass.states.async_set(SOURCE, "playing", playing(media_title="Next Episode"))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass)).attributes["media_title"] == "Next Episode"


async def test_falls_back_when_mapped_player_off(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.zones[1].input_name = "ATV"
    hass.states.async_set(SOURCE, "playing", playing())
    await setup_mapped(hass, avr)

    for off_state in ("off", "idle", "unavailable"):
        hass.states.async_set(SOURCE, off_state, {})
        await hass.async_block_till_done()
        attrs = hass.states.get(entity_id(hass)).attributes
        assert attrs["media_title"] == "ATV"
        assert "media_artist" not in attrs


async def test_falls_back_when_mapped_player_missing(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.zones[1].input_name = "ATV"
    await setup_mapped(hass, avr)

    assert hass.states.get(entity_id(hass)).attributes["media_title"] == "ATV"


async def test_unmapped_source_uses_defaults(hass: HomeAssistant) -> None:
    avr = mock_connection()  # input is "HDMI 1", not mapped
    hass.states.async_set(SOURCE, "playing", playing())
    await setup_mapped(hass, avr)

    attrs = hass.states.get(entity_id(hass)).attributes
    assert attrs["media_title"] == "HDMI 1"
    assert "media_artist" not in attrs


async def test_switching_source_clears_mirrored_data(hass: HomeAssistant) -> None:
    avr = mock_connection()
    zone = avr.protocol.zones[1]
    zone.input_name = "ATV"
    hass.states.async_set(SOURCE, "playing", playing())
    await setup_mapped(hass, avr)
    assert hass.states.get(entity_id(hass)).attributes["media_artist"] == "Apple TV+"

    zone.input_name = "HDMI 1"
    hass.states.async_set(SOURCE, "playing", playing(media_title="Other"))
    await hass.async_block_till_done()

    attrs = hass.states.get(entity_id(hass)).attributes
    assert attrs["media_title"] == "HDMI 1"
    assert "media_artist" not in attrs


async def test_cover_art_hash_ignores_access_token(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.zones[1].input_name = "ATV"
    picture = "/api/media_player_proxy/media_player.lounge?token={}&cache=abc123"
    hass.states.async_set(SOURCE, "playing", playing(entity_picture=picture.format("t1")))
    await setup_mapped(hass, avr)

    entity = hass.data["media_player"].get_entity(entity_id(hass))
    first = entity.media_image_hash
    assert first is not None

    hass.states.async_set(SOURCE, "playing", playing(entity_picture=picture.format("t2")))
    await hass.async_block_till_done()
    assert entity.media_image_hash == first


async def test_cover_art_delegates_to_mapped_player(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.zones[1].input_name = "ATV"
    hass.states.async_set(SOURCE, "playing", playing(entity_picture="/x?cache=1"))
    await setup_mapped(hass, avr)

    source_entity = AsyncMock()
    source_entity.async_get_media_image.return_value = (b"img", "image/jpeg")
    entity = hass.data["media_player"].get_entity(entity_id(hass))
    with patch.object(
        hass.data["media_player"], "get_entity", return_value=source_entity
    ):
        assert await entity.async_get_media_image() == (b"img", "image/jpeg")
        source_entity.async_get_media_image.assert_awaited_once()


async def test_cover_art_none_without_mapping(hass: HomeAssistant) -> None:
    avr = mock_connection()
    await setup_mapped(hass, avr)

    entity = hass.data["media_player"].get_entity(entity_id(hass))
    assert await entity.async_get_media_image() == (None, None)
    assert entity.media_image_hash is None


async def test_options_change_reloads_entry(hass: HomeAssistant) -> None:
    avr = mock_connection()
    entry = await setup_mapped(hass, avr, mapping={})

    with patch("anthemav.Connection.create", AsyncMock(return_value=avr)) as create:
        hass.config_entries.async_update_entry(
            entry, options={CONF_SOURCE_PLAYERS: {"HDMI 1": SOURCE}}
        )
        await hass.async_block_till_done()
    create.assert_awaited_once()
    assert er.async_get(hass).async_get_entity_id("media_player", DOMAIN, MAC)


VALUES = {"format": "4K Multi PCM", "app": "YouTube", "source": "ATV", "artist": ""}


def test_render_app_name_combines_format_and_app() -> None:
    assert render_app_name("{format} - {app}", VALUES) == "4K Multi PCM - YouTube"


def test_render_app_name_drops_missing_values_and_separators() -> None:
    assert render_app_name("{format} - {app}", {**VALUES, "app": ""}) == "4K Multi PCM"
    assert render_app_name("{app} | {format}", {**VALUES, "app": ""}) == "4K Multi PCM"


def test_render_app_name_custom_format() -> None:
    assert (
        render_app_name("{source}: {app} ({format})", VALUES)
        == "ATV: YouTube (4K Multi PCM)"
    )


def test_render_app_name_empty_result_is_empty() -> None:
    assert render_app_name("{artist}", VALUES) == ""


async def test_app_name_combines_format_and_mapped_app(hass: HomeAssistant) -> None:
    avr = mock_connection()
    zone = avr.protocol.zones[1]
    zone.input_name = "ATV"
    zone.input_format = "4K Multi PCM"
    hass.states.async_set(SOURCE, "playing", playing(app_name="YouTube"))
    await setup_mapped(hass, avr)

    assert hass.states.get(entity_id(hass)).attributes["app_name"] == "4K Multi PCM - YouTube"


async def test_app_name_without_mapped_app_is_format_only(hass: HomeAssistant) -> None:
    avr = mock_connection()
    zone = avr.protocol.zones[1]
    zone.input_name = "ATV"
    zone.input_format = "4K Multi PCM"
    hass.states.async_set(SOURCE, "playing", playing())
    await setup_mapped(hass, avr)

    assert hass.states.get(entity_id(hass)).attributes["app_name"] == "4K Multi PCM"


async def test_app_name_uses_configured_format(hass: HomeAssistant) -> None:
    avr = mock_connection()
    zone = avr.protocol.zones[1]
    zone.input_name = "ATV"
    zone.input_format = "PCM"
    hass.states.async_set(SOURCE, "playing", playing(app_name="YouTube"))
    await setup_mapped(
        hass, avr, extra_options={CONF_APP_NAME_FORMAT: "{app} via {source} ({format})"}
    )

    assert hass.states.get(entity_id(hass)).attributes["app_name"] == "YouTube via ATV (PCM)"


async def test_app_name_falls_back_to_format_when_player_off(hass: HomeAssistant) -> None:
    avr = mock_connection()
    zone = avr.protocol.zones[1]
    zone.input_name = "ATV"
    zone.input_format = "4K Multi PCM"
    hass.states.async_set(SOURCE, "off", {"app_name": "YouTube"})
    await setup_mapped(hass, avr)

    assert hass.states.get(entity_id(hass)).attributes["app_name"] == "4K Multi PCM"


async def test_sound_mode_reflects_listening_mode(hass: HomeAssistant) -> None:
    avr = mock_connection()
    await setup_mapped(hass, avr)

    state = hass.states.get(entity_id(hass))
    assert state.attributes["sound_mode"] == "AnthemLogic Music"
    assert state.attributes["sound_mode_list"] == [
        "None",
        "AnthemLogic Cinema",
        "AnthemLogic Music",
    ]


async def test_sound_mode_uses_model_numbering(hass: HomeAssistant) -> None:
    # On x40 models 03 is Dolby Surround, not the x20 "PLII Movie" the
    # library's text lookup would report.
    avr = mock_connection()
    avr.protocol._alm_number = {"None": 0, "Dolby Surround": 3}
    avr.protocol.audio_listening_mode_list = ["None", "Dolby Surround"]
    avr.protocol.audio_listening_mode = "03"
    await setup_mapped(hass, avr)

    assert hass.states.get(entity_id(hass)).attributes["sound_mode"] == "Dolby Surround"


async def test_sound_mode_unknown_until_reported(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.audio_listening_mode = ""
    await setup_mapped(hass, avr)

    assert hass.states.get(entity_id(hass)).attributes.get("sound_mode") is None


async def test_select_sound_mode_sets_listening_mode(hass: HomeAssistant) -> None:
    avr = mock_connection()
    await setup_mapped(hass, avr)

    await hass.services.async_call(
        "media_player",
        "select_sound_mode",
        {"entity_id": entity_id(hass), "sound_mode": "AnthemLogic Cinema"},
        blocking=True,
    )
    assert avr.protocol.audio_listening_mode_text == "AnthemLogic Cinema"


async def test_no_sound_mode_when_unsupported(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.support_audio_listening_mode = False
    await setup_mapped(hass, avr)

    attrs = hass.states.get(entity_id(hass)).attributes
    assert "sound_mode" not in attrs
    assert "sound_mode_list" not in attrs
    assert not attrs["supported_features"] & MediaPlayerEntityFeature.SELECT_SOUND_MODE
