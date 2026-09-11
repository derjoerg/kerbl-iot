"""Read current SmartCoop values from the Kerbl IoT API."""

import argparse
import asyncio
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kerbl_iot import DoorState, KerblIOT, KerblIOTApi


def parse_args() -> argparse.Namespace:
    """Parse explicit commands for the live test."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--toggle-light",
        action="store_true",
        help="Toggle the light of the selected SmartCoop.",
    )
    parser.add_argument(
        "--toggle-feeder",
        action="store_true",
        help="Start or stop the feeder of the selected SmartCoop.",
    )
    parser.add_argument(
        "--toggle-door",
        action="store_true",
        help="Open or close the door of the selected SmartCoop.",
    )
    parser.add_argument(
        "--show-logs",
        action="store_true",
        help="Show active SmartCoop log entries.",
    )
    parser.add_argument(
        "--acknowledge-error",
        type=int,
        metavar="ERROR_CODE",
        action="append",
        help="Acknowledge an active error code; may be used more than once.",
    )
    parser.add_argument(
        "--coop-id",
        help="SmartCoop ID to use when more than one device is available.",
    )
    return parser.parse_args()


async def main() -> None:
    """Authenticate using environment variables and print device readings."""
    args = parse_args()
    email = os.environ.get("KERBL_EMAIL")
    password = os.environ.get("KERBL_PASSWORD")
    if not email or not password:
        raise SystemExit(
            "Set KERBL_EMAIL and KERBL_PASSWORD before running this script."
        )
    command_count = sum(
        bool(option)
        for option in (
            args.toggle_light,
            args.toggle_feeder,
            args.toggle_door,
            args.acknowledge_error,
        )
    )
    if command_count > 1:
        raise SystemExit("Use only one device command per run.")

    async with KerblIOT(KerblIOTApi(email=email, password=password)) as kerbl:
        coops = kerbl.smart_coops
        await kerbl.connect_websocket()
        print(f"WebSocket connected: {kerbl.api.websocket_connected}")

        if (
            args.toggle_light
            or args.toggle_feeder
            or args.toggle_door
            or args.acknowledge_error
        ):
            if args.coop_id:
                selected_coop = next(
                    (coop for coop in coops if coop.id == args.coop_id), None
                )
                if selected_coop is None:
                    raise SystemExit(f"No SmartCoop found with ID: {args.coop_id}")
            elif len(coops) == 1:
                selected_coop = coops[0]
            else:
                raise SystemExit(
                    "Use --coop-id when toggling the light with multiple SmartCoops."
                )

            if args.acknowledge_error:
                print(
                    f"Acknowledging error codes {args.acknowledge_error} "
                    f"for: {selected_coop.name}"
                )
                result = await selected_coop.acknowledge_errors(args.acknowledge_error)
                if not result.success:
                    raise SystemExit("The error acknowledgement was not accepted.")
                print(f"Error acknowledgement accepted; command count: {result.command_count}")
                await kerbl.load()
                coops = kerbl.smart_coops
            else:
                if args.toggle_door:
                    if selected_coop.door.state is DoorState.CLOSED:
                        expected_door_state = DoorState.OPENING
                    elif selected_coop.door.state is DoorState.OPEN:
                        expected_door_state = DoorState.CLOSING
                    else:
                        state_name = (
                            selected_coop.door.state.name
                            if selected_coop.door.state is not None
                            else "unknown"
                        )
                        raise SystemExit(
                            f"Door is {state_name}; do not toggle it while its state is uncertain."
                        )

                command_name = (
                    "light"
                    if args.toggle_light
                    else "door"
                    if args.toggle_door
                    else "feeder"
                )
                print(f"Sending {command_name}-toggle command for: {selected_coop.name}")
                result = (
                    await selected_coop.light.press()
                    if args.toggle_light
                    else await selected_coop.door.press()
                    if args.toggle_door
                    else await selected_coop.feeder.press()
                )
                if not result.success:
                    raise SystemExit(f"The {command_name}-toggle command was not accepted.")
                print(f"{command_name.capitalize()}-toggle command accepted; command count: {result.command_count}")
                if args.toggle_light and selected_coop.light.is_on is None:
                    print("The current light state is unavailable; cannot verify the toggle.")
                elif args.toggle_feeder and selected_coop.feeder.feeding_in_progress is None:
                    print("The current feeding state is unavailable; cannot verify the toggle.")
                else:
                    expected_state = (
                        not selected_coop.light.is_on
                        if args.toggle_light
                        else expected_door_state
                        if args.toggle_door
                        else not selected_coop.feeder.feeding_in_progress
                    )
                    print(f"Waiting for the SmartCoop to report the new {command_name} state...")
                    confirmed_coop = (
                        await selected_coop.light.wait_for_state(is_on=expected_state)
                        if args.toggle_light
                        else await selected_coop.door.wait_for_state(state=expected_state)
                        if args.toggle_door
                        else await selected_coop.feeder.wait_for_state(
                            in_progress=expected_state
                        )
                    )
                    state_name = "on" if args.toggle_light and confirmed_coop.light.is_on else "off"
                    if args.toggle_door:
                        state_name = confirmed_coop.door.state.name
                    elif args.toggle_feeder:
                        state_name = "active" if confirmed_coop.feeder.feeding_in_progress else "inactive"
                    print(f"SmartCoop confirmed the {command_name} is {state_name}.")
                await kerbl.load()
                coops = kerbl.smart_coops

        if args.show_logs:
            for coop in coops:
                active_logs = [
                    log
                    for log in kerbl.get_smart_coop_logs(coop.id)
                    if log.active
                ]
                print(f"Active logs for {coop.name}: {len(active_logs)}")
                for log in active_logs:
                    print(
                        f"  {log.date} {log.time} [{log.level}] "
                        f"{log.error_key} "
                        f"(code: {log.error_code}; {log.error_key})"
                    )

    print(f"SmartCoops found: {len(coops)}")
    for coop in coops:
        print()
        print(f"Name:             {coop.name}")
        print(f"Online:           {coop.online}")
        print(f"Air temperature:  {coop.air_temperature} C")
        print(f"Water temperature:{coop.water_heater.water_temperature} C")
        print(f"Light dim value:  {coop.light.current_dim_value}")
        print(f"Feeding in progress: {coop.feeder.feeding_in_progress}")
        print(f"Feeding active:   {coop.feeder.feeding_active}")
        print(f"Feeding locked:   {coop.feeder.feeding_locked}")
        print(f"Outdoor brightness:{coop.brightness.current_brightness}")
        print(
            "Door state:       "
            f"{coop.door.state.name if coop.door.state is not None else 'unknown'}"
        )


if __name__ == "__main__":
    asyncio.run(main())