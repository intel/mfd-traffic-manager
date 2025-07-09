# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Traffic manager module."""

import concurrent
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, TYPE_CHECKING, Dict, Callable, Any

from mfd_common_libs import add_logging_level, log_levels

from mfd_traffic_manager.exceptions import TrafficManagerModuleException

if TYPE_CHECKING:
    from mfd_traffic_manager.stream import Stream

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class TrafficManager:
    """Class for Traffic Manager."""

    streams: List["Stream"]

    def __init__(self):
        """Initialize the Traffic Manager."""
        self.streams = []

    def start_all(self) -> None:
        """Start all streams added to the manager."""
        with ThreadPoolExecutor(max_workers=len(self.streams)) as executor:
            futures = {executor.submit(stream.start): stream for stream in self.streams}
            for future in concurrent.futures.as_completed(futures):
                future.result()

    def start(self, name: str, delay: Optional[int] = None) -> None:
        """
        Start stream with given name.

        :param name: Name of stream to start.
        :param delay: time between server and client stops
        """
        for stream in self.streams:
            if name == stream.name:
                stream.start(delay)
                return
        raise TrafficManagerModuleException(f"Not found stream with name '{name}'")

    def stop_all(self) -> None:
        """Stop all streams added to the manager."""
        with ThreadPoolExecutor(max_workers=len(self.streams)) as executor:
            futures = {executor.submit(stream.stop): stream for stream in self.streams}
            for future in concurrent.futures.as_completed(futures):
                future.result()

    def stop(self, name: str, delay: Optional[int] = None) -> None:
        """
        Stop stream with given name.

        :param name: Name of stream to stop.
        :param delay: time between server and client stops
        :raises TrafficManagerModuleException: if not found stream
        """
        for stream in self.streams:
            if name == stream.name:
                stream.stop(delay)
                return
        raise TrafficManagerModuleException(f"Not found stream with name '{name}'")

    def run_all(self, duration: int) -> None:
        """
        Run all streams added to the manager.

        :param duration: Duration of stream
        """
        with ThreadPoolExecutor(max_workers=len(self.streams)) as executor:
            futures = {executor.submit(stream.run, duration=duration): stream for stream in self.streams}
            for future in concurrent.futures.as_completed(futures):
                future.result()

    def run(self, name: str, duration: int) -> None:
        """
        Run stream with given name.

        :param name: Name of stream to run.
        :param duration: Duration of stream
        :raises TrafficManagerModuleException: if not found stream
        """
        for stream in self.streams:
            if name == stream.name:
                stream.run(duration=duration)
                return
        raise TrafficManagerModuleException(f"Not found stream with name '{name}'")

    def validate_all(
        self,
        common_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
        *,
        server_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
        clients_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
    ) -> bool:
        """
        Validate all streams using criteria.

        Validation criteria has 3 parameters, common and server/clients.
        Parameters define validation criteria for server and clients as common, for server and for clients.
        It means:
         if passed just common_validation_criteria, criteria will be used for server and clients.
         User can pass independently criteria for server and for clients, if required.

        :param common_validation_criteria: Dict containing validation criteria for server and clients
        :param server_validation_criteria: Dict containing validation criteria for server
        :param clients_validation_criteria: Dict containing validation criteria for clients
        :return: Status of validation.
        """
        with ThreadPoolExecutor(max_workers=len(self.streams)) as executor:
            futures = {
                executor.submit(
                    stream.validate,
                    common_validation_criteria=common_validation_criteria,
                    server_validation_criteria=server_validation_criteria,
                    clients_validation_criteria=clients_validation_criteria,
                ): stream
                for stream in self.streams
            }
            for future in concurrent.futures.as_completed(futures):
                if not future.result():
                    logger.log(level=log_levels.MODULE_DEBUG, msg="Validation failed in one of Streams")
                    return False
            return True

    def validate(
        self,
        name: str,
        common_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
        *,
        server_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
        clients_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
    ) -> bool:
        """
        Validate stream with given name using criteria.

        Validation criteria has 3 parameters, common and server/clients.
        Parameters define validation criteria for server and clients, for server and for clients.
        It means:
             if passed just common_validation_criteria, criteria will be used for server and clients.
             User can pass independently criteria for server and for clients, if required.

        :param name: Name of stream to validate.
        :param common_validation_criteria: Dict containing validation criteria for server and clients
        :param server_validation_criteria: Dict containing validation criteria for server
        :param clients_validation_criteria: Dict containing validation criteria for clients
        :raises TrafficManagerModuleException: if not found stream
        :raises ValueError: If passed not supported combination of criteria.
        :return: Status of validation.
        """
        for stream in self.streams:
            if name == stream.name:
                return stream.validate(
                    common_validation_criteria=common_validation_criteria,
                    server_validation_criteria=server_validation_criteria,
                    clients_validation_criteria=clients_validation_criteria,
                )
        raise TrafficManagerModuleException(f"Not found stream with name '{name}'")

    def add_stream(self, stream: "Stream") -> None:
        """
        Add stream to the manager.

        :param stream: Stream to add
        """
        self.streams.append(stream)
