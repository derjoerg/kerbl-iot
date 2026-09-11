# Kerbl IoT

Async Python client for Kerbl IoT devices.

`KerblIOTApi` owns authentication, HTTP, token refresh, and Socket.IO transport.
`KerblIOT` loads devices and dispatches their live updates. Device actions belong to
their respective model classes.

```python
import asyncio
import os

from kerbl_iot import KerblIOT, KerblIOTApi


async def main() -> None:
    async with KerblIOT(
        KerblIOTApi(
            email=os.environ["KERBL_EMAIL"],
            password=os.environ["KERBL_PASSWORD"],
        )
    ) as kerbl:
        await kerbl.connect_websocket()

        coop = kerbl.smart_coops[0]
        print(coop.name, coop.air_temperature, coop.door.state)
        await coop.light.turn_on()
        await coop.door.close()


asyncio.run(main())
```

## Releasing to PyPI

When a version change is pushed to `main`, GitHub Actions first runs the complete
`ci.yml` workflow. Only after CI succeeds does `release.yml` create a matching tag
and GitHub Release. The published release then triggers `publish.yml` for PyPI.
Before the first release, configure PyPI Trusted Publishing for the
`derjoerg/kerbl-iot` repository and the `.github/workflows/publish.yml` workflow,
using the `pypi` environment.

To release a new version, update the `version` in `pyproject.toml` and merge that
change into `main`. The version must not already exist on PyPI, and the matching
`vX.Y.Z` tag must not already exist in GitHub.

## Error reason reference

`SmartCoopLog` exposes the API's raw `error_key` and `error_code`. Applications
should translate the key in their own presentation layer. The following table
preserves the German translations previously included in this library for
reference:

| API error key | Former German translation |
| --- | --- |
| `errorReason.doorLocked` | Klappe verriegelt |
| `errorReason.doorClosingSoon` | Klappe schliesst bald |
| `errorReason.feederLocked` | Futterautomat gesperrt |
| `errorReason.batteryLow` | Akku schwach |
| `errorReason.waterHeaterActive` | Wasserheizung aktiv |
| `errorReason.waterEmpty` | Wasser leer |
| `errorReason.feederError` | Futterautomatenstoerung |
| `errorReason.feedEmpty` | Futter leer |
| `errorReason.batteryEmpty` | Akku leer |
| `errorReason.doorError` | Klappenstoerung |
| `errorReason.waterTemperatureLow` | Wassertemperatur zu niedrig |
| `errorReason.externalLightError` | Fremdlichtstoerung |
| `errorReason.timeError` | Uhrzeit muss eingestellt werden |
| `errorReason.flashError` | Flash-Fehler |
