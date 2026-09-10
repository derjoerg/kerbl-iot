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
