# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Stream."""

import concurrent
from concurrent.futures import ThreadPoolExecutor
import logging
from time import sleep
from typing import List, TYPE_CHECKING, Optional, Dict, Callable, Any, Tuple
from mfd_common_libs import add_logging_level, log_levels

from mfd_traffic_manager.utils import reserve_port, unreserve_port

if TYPE_CHECKING:
    from mfd_traffic_manager.base import Traffic

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class Stream:
    """Stream class."""

    def __init__(
        self,
        clients: List["Traffic"],
        server: "Traffic",
        name: Optional[str] = "Stream",
        port: Optional[int] = None,
        port_find_tries: int = 10,
    ) -> None:
        """
        Create stream.

        :param clients: List of client Traffic objects.
        :param server: Server Traffic object
        :param name: Optional name of stream, usable for starting/stopping by name
        :param port: Optional starting port, if traffic uses port stream will check and reserve port.
        :param port_find_tries: Value of how many tries to find next free port
        """
        self.name = name
        self.clients = clients
        self.server = server
        self.all_traffics = [self.server] + self.clients
        if port is not None:
            if not hasattr(self.server, "_connection") and not hasattr(self.server, "port"):
                logger.log(level=log_levels.MODULE_DEBUG, msg="Traffic is not using port, skipping reservation.")
            else:
                self.port_reservation = reserve_port(self.server._connection, port, count=port_find_tries)
                # todo check on each machine if port is free
                self.port = self.port_reservation.port
                self.server.port = self.port
                for client in self.clients:
                    client.port = self.port

    def start(self, delay: Optional[int] = None) -> None:
        """Start stream.

        :param delay: time between server and client starts
        """
        # start server
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(self.server.start)}
            for future in concurrent.futures.as_completed(futures):
                future.result()

        if delay:
            sleep(int(delay))

        # start clients
        with ThreadPoolExecutor(max_workers=len(self.clients)) as executor:
            futures = {executor.submit(traffic.start): traffic for traffic in self.clients}
            for future in concurrent.futures.as_completed(futures):
                future.result()

    def stop(self, delay: Optional[int] = None) -> None:
        """Stop stream.

        :param delay: time between server and client stops
        """
        # stop clients
        with ThreadPoolExecutor(max_workers=len(self.clients)) as executor:
            futures = {executor.submit(traffic.stop): traffic for traffic in self.clients}
            for future in concurrent.futures.as_completed(futures):
                future.result()

        if delay:
            sleep(int(delay))

        # stop server
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(self.server.stop)}
            for future in concurrent.futures.as_completed(futures):
                future.result()

        self._stop_reservation()

    def _stop_reservation(self) -> None:
        if hasattr(self, "port_reservation"):
            with ThreadPoolExecutor(max_workers=1) as executor:
                futures = {executor.submit(unreserve_port, self.port_reservation)}
                for future in concurrent.futures.as_completed(futures):
                    future.result()

    def run(self, duration: int) -> None:
        """
        Run stream.

        :param duration: Duration time (in secs)
        """
        # run server
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(self.server.run, duration)}
            for future in concurrent.futures.as_completed(futures):
                future.result()

        # run all clients
        with ThreadPoolExecutor(max_workers=len(self.clients)) as executor:
            futures = {executor.submit(traffic.run, duration): traffic for traffic in self.clients}
            for future in concurrent.futures.as_completed(futures):
                future.result()

        # stop server
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(self.server.stop)}
            for future in concurrent.futures.as_completed(futures):
                future.result()

        self._stop_reservation()

    def validate(
        self,
        common_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
        *,
        server_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
        clients_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
    ) -> bool:
        """
        Validate stream.

        Validation criteria has 3 parameters, common and server/clients.
        Parameters define validation criteria for server and clients as common, for server and for clients.
        It means:
         if passed just common_validation_criteria, criteria will be used for server and clients.
         User can pass independently criteria for server and for clients, if required.

        :param common_validation_criteria: Dict containing validation criteria for server and clients
        :param server_validation_criteria: Dict containing validation criteria for server
        :param clients_validation_criteria: Dict containing validation criteria for clients
        :raises ValueError: If passed not supported combination of criteria.
        :return: True or False
        """
        self._verify_validation_criteria(
            common_validation_criteria, server_validation_criteria, clients_validation_criteria
        )
        server_criteria, clients_criteria = self._set_default_criteria(
            common_validation_criteria, server_validation_criteria, clients_validation_criteria
        )

        # validate all traffics
        with ThreadPoolExecutor(max_workers=len(self.all_traffics)) as executor:
            futures = {
                executor.submit(traffic.validate, server_criteria)
                if traffic == self.server
                else executor.submit(traffic.validate, clients_criteria): traffic
                for traffic in self.all_traffics
            }
            for future in concurrent.futures.as_completed(futures):
                if not future.result():
                    logger.log(
                        level=log_levels.MODULE_DEBUG, msg=f"Validation failed in one of Stream {self.name} traffics"
                    )
                    return False
            return True

    def _set_default_criteria(
        self,
        common_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]],
        server_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]],
        clients_validation_criteria: Optional[Dict[Callable, Dict[str, Any]]],
    ) -> Tuple[Dict[Callable, Dict[str, Any]], Dict[Callable, Dict[str, Any]]]:
        """
        Set default criteria for not passed dictionaries.

        Server and client criteria will be set as common criteria if not passed server or client criteria.

        :return: Tuple with updated server and client criteria.
        """
        common_criteria = (
            {lambda r, x: x: {"x": True}} if not common_validation_criteria else common_validation_criteria
        )  # default criteria which pass always
        server_criteria = common_criteria.copy() if server_validation_criteria is None else server_validation_criteria
        clients_criteria = (
            common_criteria.copy() if clients_validation_criteria is None else clients_validation_criteria
        )
        return server_criteria, clients_criteria

    def _verify_validation_criteria(
        self,
        common_validation_criteria: Dict[Callable, Dict[str, Any]] | None,
        server_validation_criteria: Dict[Callable, Dict[str, Any]] | None,
        clients_validation_criteria: Dict[Callable, Dict[str, Any]] | None,
    ) -> None:
        """
        Check if criteria are not overriding each other.

        Supported cases:
            only common
            only server
            only clients
            server + clients

        :raises ValueError: if validation failed.
        """
        if all([common_validation_criteria, server_validation_criteria, clients_validation_criteria]):
            raise ValueError("Passing common, server and clients criteria together is not supported.")
        if common_validation_criteria and (server_validation_criteria or clients_validation_criteria):
            raise ValueError("Passing common and server or common and clients criteria together is not supported.")

    @property
    def completed(self) -> bool:
        """Check if all the traffics stopped running."""
        return (
            all(client.started for client in self.clients)
            and self.server.started
            and not any(client.running for client in self.clients)
            and not self.server.running
        )

    @property
    def started(self) -> bool:
        """Check if all the traffics were started."""
        return all(client.started for client in self.clients) and self.server.started
