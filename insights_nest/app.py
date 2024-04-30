import argparse
import logging
import os
import sys
from typing import Optional

from insights_nest import _action
from insights_nest._core import egg

if os.environ.get("NEST_DEBUG_STDERR", "").lower() in ("true", "1"):
    LOG_FORMAT = (
        "\033[32;1m{levelname}\033[0m \033[32m{asctime}\033[0m\n"
        "\033[33m{pathname}:{lineno}\033[0m\n{message}\n"
    )

    logging.basicConfig(
        level=logging.DEBUG,
        style="{",
        format=LOG_FORMAT,
    )
else:
    LOG_FORMAT = "[{levelname:<7}] {pathname}:{lineno} {message}"

    # TODO Log to file


logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()

    # Modifier flags
    parser.add_argument(
        "--format",
        choices=_action.Format.choices(),
        default=_action.Format.choices()[0],
        type=_action.Format.parse,
        help="output format",
    )

    # Non-terminal commands
    parser.add_argument(
        "--no-egg-update",
        action="store_true",
        default=False,
        help="do not check for egg updates",
    )
    parser.add_argument(
        "--group",
        help="assign the host to a group",
    )

    # Terminal commands
    parser.add_argument(
        "--register",
        action="store_true",
        default=False,
        help="register host to Insights",
    )
    parser.add_argument(
        "--unregister",
        action="store_true",
        default=False,
        help="unregister host from Insights",
    )
    parser.add_argument(
        "--checkin",
        action="store_true",
        default=False,
        help="send a light check-in message to Insights",
    )

    args, _ = parser.parse_known_args()
    if args.no_egg_update:
        logger.debug("Skipping egg update step.")
    else:
        # TODO Should we expose this through CLI or flag?
        egg.update(force=False)
    if args.group:
        # FIXME Implement --group.
        logger.warning("--group: not implemented, ignoring.")

    result: Optional[int] = None
    if args.register:
        result = _action.Register.run(format=args.format)
    if args.unregister:
        result = _action.Unregister.run(format=args.format)
    if args.checkin:
        result = _action.Checkin.run(format=args.format)

    if result is not None:
        logger.info(f"Quitting with status code {result}.")
        sys.exit(result)

    parser.print_help()


if __name__ == "__main__":
    main()
