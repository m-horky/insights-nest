import enum
import glob
import json
import logging
import os.path
import shutil
import sys
import datetime
import uuid
from typing import Optional

from insights_nest._core import egg, system
from insights_nest.api import inventory, ingress

logger = logging.getLogger(__name__)


class Format(enum.Enum):
    HUMAN: str = "HUMAN"
    JSON: str = "JSON"

    @classmethod
    def parse(cls, value: str) -> "Format":
        value = value.lower()
        if value == "human":
            return cls.HUMAN
        if value == "json":
            return cls.JSON
        raise RuntimeError(f"Unknown format: {format}")

    def __str__(self):
        return self.value.lower()

    @classmethod
    def choices(cls) -> list["Format"]:
        return [cls.HUMAN, cls.JSON]


def pprint(message: str, /, format: Format, ok: bool) -> int:
    """Print a message in requested format and return zero or non-zero code."""
    if format == Format.JSON:
        message = json.dumps({"message": message, "ok": ok})
    if format == Format.HUMAN:
        if not ok:
            message = f"Error: {message}"

    print(message, file=sys.stdout)
    return 0 if ok else 1


class Register:
    @classmethod
    def run(cls, *, format: Format) -> int:
        if system.get_inventory_host() is not None:
            return pprint("This host is already registered.", format=format, ok=False)

        logger.info("Registering the host.")

        try:
            egg.Egg.load()
            import insights.anchor.v1
        except ImportError:
            logger.exception("Could not load the Insights Core.")
            return pprint("Could not load the Insights Core.", format=format, ok=False)

        # TODO Query for sub-man certificate ID instead.
        with open("/etc/insights-client/machine-id", "w") as f:
            machine_id = str(uuid.uuid4())
            logger.info(f"Generated machine-id: {machine_id}.")
            f.write(machine_id)

        try:
            facts_archive: insights.anchor.v1.SimpleResult = (
                insights.anchor.v1.CanonicalFacts().run()
            )
        except Exception:
            logger.exception("Could not collect canonical facts.")
            return pprint("Could not collect canonical facts.", format=format, ok=False)

        try:
            advisor_archive: insights.anchor.v1.ArchiveResult = insights.anchor.v1.Advisor().run()
        except Exception:
            logger.exception("Could not collect Advisor data.")
            return pprint("Could not collect Advisor data.", format=format, ok=False)

        try:
            _: ingress.UploadResponse = ingress.Ingress().upload(
                advisor_archive.path,
                advisor_archive.content_type,
                facts_archive.data,
            )
        except Exception:
            logger.exception("Could not upload data to Inventory.")
            return pprint("Could not register with Inventory.", format=format, ok=False)

        logger.debug("Removing file /etc/insights-client/.unregistered")
        if os.path.exists("/etc/insights-client/.unregistered"):
            os.remove("/etc/insights-client/.unregistered")

        logger.debug("Writing /etc/insights-client/.registered")
        with open("/etc/insights-client/.registered", "w") as f:
            f.write(datetime.datetime.isoformat(datetime.datetime.now(tz=datetime.timezone.utc)))

        # TODO Enable systemd services

        return pprint("The host has been registered.", format=format, ok=True)


class Unregister:
    @classmethod
    def run(cls, *, format: Format) -> int:
        logger.info("Unregistering the host.")
        # We may not be sure if the host has been registered or not, since the registration
        # is tied to several weak conditions.
        was_registered: bool = False

        host: Optional[inventory.Host] = system.get_inventory_host()
        if host is not None:
            logger.debug("Deleting the host from Inventory.")
            inventory.Inventory().delete_host(host.id)
            was_registered = True

        for path in [
            "/etc/insights-client/machine-id",
            "/etc/insights-client/.registered",
        ]:
            if os.path.exists(path):
                was_registered = True

        for path in [
            "/etc/insights-client/machine-id",
            "/etc/insights-client/.registered",
            "/etc/rhsm/facts/insights-client.facts",
            *glob.glob("/var/lib/insights/*"),
        ]:
            if os.path.isdir(path):
                logger.debug(f"Removing directory {path}.")
                shutil.rmtree(path)
                continue
            if os.path.exists(path):
                logger.debug(f"Removing file {path}.")
                os.remove(path)
                continue

        if not os.path.exists("/etc/insights-client/.unregistered"):
            was_registered = True
            logger.debug("Writing /etc/insights-client/.unregistered")
            with open("/etc/insights-client/.unregistered", "w") as f:
                f.write(
                    datetime.datetime.isoformat(datetime.datetime.now(tz=datetime.timezone.utc))
                )

        # TODO Disable systemd services

        if was_registered:
            return pprint("The host has been unregistered.", format=format, ok=True)
        else:
            return pprint("The host is already unregistered.", format=format, ok=False)


class Checkin:
    @classmethod
    def run(cls, *, format: Format):
        if system.get_inventory_host() is None:
            return pprint("This host is not registered.", format=format, ok=False)

        logger.info("Checking in.")

        try:
            egg.Egg.load()
            import insights.anchor.v1
        except ImportError:
            logger.exception("Could not load the Insights Core.")
            return pprint("Could not load the Insights Core.", format=format, ok=False)

        try:
            facts_archive: insights.anchor.v1.SimpleResult = (
                insights.anchor.v1.CanonicalFacts().run()
            )
        except Exception:
            logger.exception("Could not collect canonical facts.")
            return pprint("Could not collect canonical facts.", format=format, ok=False)

        try:
            res: inventory.Host = inventory.Inventory().checkin(facts_archive.data)
            print(res)
        except Exception:
            logger.exception("Could not check in with Inventory.")
            return pprint("Could not check in with Inventory.", format=format, ok=False)

        pprint("Successfully checked in.", format=format, ok=True)