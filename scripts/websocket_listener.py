"""Print live SmartCoop updates received through the Kerbl IoT WebSocket."""

import argparse
import asyncio
from datetime import datetime
import os
from typing import Any

from kerbl_iot import KerblIOT, KerblIOTApi, SmartCoop


def parse_args() -> argparse.Namespace:
    """Parse listener options."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show Socket.IO transport diagnostics.",
    )
    return parser.parse_args()


async def print_smart_coop_update(coop: SmartCoop) -> None:
    """Print the relevant values of one incoming SmartCoop update."""
    door_state = coop.door_state.name if coop.door_state is not None else "UNKNOWN"
    print(
        f"[{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"{coop.name}: door={door_state}, light={coop.light_dim_value}, "
        f"feeding={coop.feeding_in_progress}, air={coop.air_temperature} C, "
        f"water={coop.water_temperature} C, voltage={coop.current_voltage} V",
        flush=True,
    )


async def print_socket_event(event: str, data: Any) -> None:
    """Print Socket.IO events not handled as a SmartCoop state update."""
    if event != "smart-coop_update":
        print(f"Socket.IO event: {event} ({type(data).__name__})", flush=True)


async def main() -> None:
    """Connect to Kerbl IoT and keep the WebSocket listener running."""
    args = parse_args()
    email = os.environ.get("KERBL_EMAIL")
    password = os.environ.get("KERBL_PASSWORD")
    if not email or not password:
        raise SystemExit(
            "Set KERBL_EMAIL and KERBL_PASSWORD before running this script."
        )

    async with KerblIOT(KerblIOTApi(email=email, password=password)) as kerbl:
        kerbl.register_smart_coop_update_callback(print_smart_coop_update)
        kerbl.api.register_socket_event_callback(print_socket_event)
        await kerbl.connect_websocket(debug=args.debug)
        if not kerbl.api.websocket_connected:
            raise RuntimeError("Kerbl WebSocket could not be connected.")
        print("WebSocket connected.", flush=True)
        print("Subscribed SmartCoops: " + ", ".join(coop.name for coop in kerbl.smart_coops), flush=True)
        print("Listening for SmartCoop updates. Press Ctrl+C to stop.", flush=True)
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("WebSocket listener stopped.")