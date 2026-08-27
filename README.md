# notiOne for Home Assistant

Device trackers for [notiOne](https://notione.pl/) Bluetooth/GPS locators, using the same unofficial cloud API as the notiOne mobile app.

This is a fork of [n4ts/ha-notione](https://github.com/n4ts/ha-notione), rewritten as a modern config-entry integration:

- Asynchronous client on Home Assistant's shared HTTP session, with TLS certificate verification enabled and request timeouts (the original disabled certificate verification).
- UI configuration (config flow) with credential validation, re-authentication on password change, and a picker for which trackers become entities.
- Registry-based `device_tracker` entities with stable unique IDs (the notiOne device ID), GPS coordinates, accuracy, battery status, and position timestamp attributes.
- No YAML configuration and no legacy `known_devices.yaml` involvement.

## Installation

### HACS (custom repository)

1. HACS → Integrations → ⋮ → **Custom repositories**.
2. Add `https://github.com/seler/ha-notione` with category **Integration**.
3. Install **notiOne**, then restart Home Assistant.

### Manual

Copy `custom_components/notione/` into your config's `custom_components/` and restart.

## Configuration

Settings → Devices & services → **Add integration** → *notiOne*. Sign in with your notiOne account, then pick the trackers to follow. The tracked set can be changed later via the integration's **Configure** dialog.

## Entity attributes

Each tracker exposes `gpstime` (UTC position timestamp), `beaconid` (notiOne device ID), `location` (reverse-geocoded street and city as reported by the API), `battery_status` (`low`/`high`), and `deviceVersion`.

## Development

```sh
docker run --rm -v "$PWD":/wt -w /wt --entrypoint bash \
  ghcr.io/home-assistant/home-assistant:2026.8.3 \
  -c "pip install -q pytest-homeassistant-custom-component trustme && python3 -m pytest tests -q"
```

## Credits and license

Original integration by [@n4ts](https://github.com/n4ts). Apache License 2.0 (see `LICENSE`).
