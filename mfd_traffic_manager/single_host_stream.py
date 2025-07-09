# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for single host stream."""

import concurrent
import logging
import typing
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

from mfd_common_libs import add_logging_level, log_levels

from mfd_traffic_manager import Stream
from mfd_traffic_manager.utils import reserve_port

if typing.TYPE_CHECKING:
    from mfd_traffic_manager import Traffic

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class SingleHostStream(Stream):
    """Class for single host stream."""

    def __init__(
        self,
        server: "Traffic",
        name: str | None = "Stream",
        port: int | None = None,
        port_find_tries: int = 10,
    ) -> None:
        """
        Create stream.

        :param server: Server Traffic object
        :param name: Optional name of stream, usable for starting/stopping by name
        :param port: Optional starting port, if traffic uses port stream will check and reserve port.
        :param port_find_tries: Value of how many tries to find the next free port
        """
        self.name = name
        self.server = server
        if port is not None:
            if not hasattr(self.server, "_connection") and not hasattr(self.server, "port"):
                logger.log(level=log_levels.MODULE_DEBUG, msg="Traffic is not using port, skipping reservation.")
            else:
                self.port_reservation = reserve_port(self.server._connection, port, count=port_find_tries)
                # todo check on each machine if port is free
                self.port = self.port_reservation.port
                self.server.port = self.port

    def start(self, **kwargs) -> None:
        """Start stream."""
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(self.server.start)}
            for future in concurrent.futures.as_completed(futures):
                future.result()

    def stop(self, **kwargs) -> None:
        """Stop stream."""
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(self.server.stop)}
            for future in concurrent.futures.as_completed(futures):
                future.result()

        self._stop_reservation()

    def run(self, duration: int) -> None:
        """
        Run stream.

        :param duration: Duration time (in secs)
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(self.server.run, duration)}
            for future in concurrent.futures.as_completed(futures):
                future.result()

        self._stop_reservation()

    def validate(self, common_validation_criteria: dict[Callable, dict[str, Any]] | None = None, **kwargs) -> bool:
        """
        Validate stream.

        :param common_validation_criteria: Dict containing validation criteria for server
        :raises ValueError: If passed a not supported combination of criteria.
        :return: True or False
        """
        server_criteria = self._set_default_criteria(common_validation_criteria)

        # validate all traffics
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(self.server.validate, server_criteria)}
            for future in concurrent.futures.as_completed(futures):
                if not future.result():
                    logger.log(
                        level=log_levels.MODULE_DEBUG, msg=f"Validation failed in one of Stream {self.name} traffics"
                    )
                    return False
            return True

    def _set_default_criteria(
        self, common_validation_criteria: dict[Callable, dict[str, Any]] | None, **kwargs
    ) -> dict[Callable, dict[str, Any]]:
        """
        Set default criteria for not passed dictionaries.

        :return: Updated criteria.
        """
        common_criteria = (
            {lambda r, x: x: {"x": True}} if not common_validation_criteria else common_validation_criteria
        )  # default criteria which pass always
        return common_criteria

    @property
    def completed(self) -> bool:
        """Check if all the traffics stopped running."""
        return self.server.started and not self.server.running

    @property
    def started(self) -> bool:
        """Check if all the traffics were started."""
        return self.server.started
