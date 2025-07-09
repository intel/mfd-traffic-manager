# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Stress traffic manager module."""

import logging
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import TYPE_CHECKING, Union, Optional, Type, Any

from mfd_common_libs import add_logging_level, log_levels

from .exceptions import StressTrafficManagerModuleExcpetion
from .manager import TrafficManager
from .stream import Stream

if TYPE_CHECKING:
    from mfd_connect import Connection
    from ipaddress import IPv4Interface, IPv6Interface
    from .base import Traffic


logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)

event = threading.Event()


class Protocols(Enum):
    """Supported protocols."""

    ICMP = "icmp"
    TCP = "tcp"
    UDP = "udp"
    SCTP = "sctp"


class CommunicationType(Enum):
    """Supported communication types."""

    BROADCAST = "broadcast"
    MULTICAST = "multicast"


class TrafficTools(Enum):
    """Supported traffic tools."""

    PING = "ping"
    IPERF2 = "iperf2"
    IPERF3 = "iperf3"
    NETPERF = "netperf"
    NETPERF_OMNI = "netperf_omni"


class StressTrafficManager(TrafficManager):
    """Class for StressTrafficManager."""

    def __init__(
        self,
        sut_connection: "Connection",
        src_ips: list[Union[str, "IPv4Interface", "IPv6Interface"]],
        dst_ip: Union[str, "IPv4Interface", "IPv6Interface"],
        clients_connections: list["Connection"],
        traffic_classes: dict[TrafficTools, dict[str, Type["Traffic"]]],
        num_streams: int,
        start_port: int = 5001,
        min_dur: int = 10,
        max_dur: int = 21600,
        min_size: int = 64,
        max_size: int = 64000,
        protocols: list[Protocols] = [Protocols.ICMP, Protocols.UDP, Protocols.TCP, Protocols.SCTP],
        traffic_tools: list[TrafficTools] = [
            TrafficTools.PING,
            TrafficTools.IPERF2,
            TrafficTools.IPERF3,
            TrafficTools.NETPERF,
        ],
        comm_type: Optional[CommunicationType] = None,
    ):
        """
        Initialize StressTrafficManager object.

        :param sut_connection: Connection object for SUT
        :param src_ips: List of IP address to be used as source addresses by clients
        :param dst_ip: IP address to be used by clients as destination address of server
        :param clients_connections: List of connection objects for clients
        :param traffic_classes: Dict of Traffic tools classes (please use TRAFFIC_CLASSES from mfd_basic_logic.traffic)
                                See stress_traffic_example.py for more details
        :param num_streams: Number of parallel streams to be executed
        :param start_port: Initial port value (raised by one for each consecutive stream created)
        :param min_dur: Minimum duration for the stream (used as a lower limit for random selection)
        :param max_dur: Maximum duration for the stream (used as higher limit for random selection)
        :param min_size: Minimum packet/message size for the traffic in the stream
                         (used as a lower limit for random selection)
        :param max_size: Maximum packet/message size for the traffic in the stream
                         (used as a higher limit for random selection)
        :param protocols: List of protocols to be used for random selection
        :param traffic_tools: List of tools to be used for random selection
        :param comm_type: Communication type: broadcast or multicast
        """
        super().__init__()
        self.sut_connection = sut_connection
        self.src_ips = src_ips
        self.dst_ip = dst_ip
        self.clients_connections = clients_connections
        self.traffic_classes = traffic_classes
        self.num_streams = num_streams
        self.min_dur = min_dur
        self.max_dur = max_dur
        self.min_size = min_size
        self.max_size = max_size
        self.protocols = protocols
        self.comm_type = comm_type
        self.traffic_tools = traffic_tools
        self.executor = ThreadPoolExecutor(max_workers=self.num_streams + 1)
        self.event = threading.Event()
        self.__paused = False
        self._results_ready = False
        self._port = start_port
        self.streams = []
        self.futures = {}

    def start_all(self) -> None:
        """Submit the specified number of streams and trigger monitoring thread to replace the completed ones."""
        self.streams.extend([self._create_random_stream() for _ in range(self.num_streams)])
        for stream in self.streams:
            duration = self._random_duration
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Starting initial stream with duration: {duration} s")
            self.futures[self.executor.submit(stream.run, duration)] = stream
        self.executor.submit(self._control_streams)

    def stop_all(self) -> None:
        """Stop running streams. To generate new traffics another instance of StressTrafficManager must be created."""
        self.event.set()
        while not self._results_ready:
            time.sleep(0.1)
        self.executor.shutdown(wait=True, cancel_futures=True)

    def pause_all(self, duration: Optional[int] = None) -> None:
        """
        Stop running streams. Traffic generation can be resumed by calling resume_all() method.

        :param duration: duration of stress traffic pause
        :raises StressTrafficManagerModuleException: If stress traffic already running
        """
        if not self._paused:
            self.event.set()
            while not self._results_ready:
                time.sleep(0.1)
            self._paused = True
            if duration is not None:
                time.sleep(duration)
                self.resume_all()
        else:
            raise StressTrafficManagerModuleExcpetion("Stress Traffic Manager is already paused.")

    def resume_all(self) -> None:
        """
        Resume the parallel execution after pause.

        :raises StressTrafficManagerModuleException: If stress traffic already running
        """
        if self._paused:
            self.event.clear()
            self.start_all()
            self._paused = False
        else:
            raise StressTrafficManagerModuleExcpetion("Stress Traffic Manager is already running.")

    def _control_streams(self) -> None:
        """Detect completed streams and replace them with new instances."""
        while not self.event.is_set():
            completed_futures = {}
            new_futures = {}
            for future, stream in self.futures.items():
                if future.done():
                    if msg := future.exception():
                        logger.log(
                            level=log_levels.MFD_INFO, msg=f"Following exception raised during Stream execution: {msg}"
                        )
                    completed_futures[future] = stream
                    new_stream = self._create_random_stream()
                    self.streams.append(new_stream)
                    duration = self._random_duration
                    logger.log(
                        level=log_levels.MODULE_DEBUG,
                        msg=f"Completed stream detected. Starting new one with duration: {duration} s",
                    )
                    new_future = self.executor.submit(new_stream.run, duration)
                    new_futures[new_future] = new_stream
            for future in completed_futures:
                del self.futures[future]
            self.futures.update(new_futures)
            time.sleep(0.1)

        logger.log(level=log_levels.MODULE_DEBUG, msg="Stopping all running streams")

        # TBD: find cleaner way of exception (PID not found) handling inside the threads, preferably in mfd-connect
        try:
            super().stop_all()
        except Exception:
            logger.log(level=log_levels.MODULE_DEBUG, msg="Exception raised during stream stopping - ignored")

        self._results_ready = True

    def stop(self, name: str) -> None:
        """Stop stream with given name."""
        raise NotImplementedError("stop() method not applicable to stress traffic manager.")

    def start(self, name: str) -> None:
        """Start stream with given name."""
        raise NotImplementedError("start() method not applicable to stress traffic manager.")

    def run(self, name: str, duration: int) -> None:
        """Run stream with given name."""
        raise NotImplementedError("run() method not applicable to stress traffic manager.")

    def run_all(self, duration: int) -> None:
        """Run all streams added to the manager."""
        raise NotImplementedError("run_all() method not applicable to stress traffic manager.")

    def _create_random_stream(self) -> Stream:
        """
        Generate stream object based on the traffic_classes dict, protocols and tools passed to the class constructor.

        :return: Newly generated stream object
        :raises StressTrafficManager: When passed incompatible protocols and tools
        """
        protocol = self._random_protocol
        if protocol == Protocols.ICMP and TrafficTools.PING not in self.traffic_tools:
            raise StressTrafficManagerModuleExcpetion("ICMP protocol selected but ping not in allowed tools.")
        elif protocol == Protocols.ICMP:
            traffic_tool = TrafficTools.PING
        elif protocol == Protocols.SCTP:
            sctp_traffics = list(
                filter(lambda x: x in [TrafficTools.IPERF3, TrafficTools.NETPERF_OMNI], self.traffic_tools)
            )
            if sctp_traffics:
                traffic_tool = random.choice(sctp_traffics)
            else:
                raise StressTrafficManagerModuleExcpetion("SCTP protocol passed but no SCTP supporting tool allowed.")
        else:
            non_icmp_traffics = [tool for tool in self.traffic_tools if tool != TrafficTools.PING]
            if non_icmp_traffics:
                traffic_tool = random.choice(non_icmp_traffics)
            else:
                raise StressTrafficManagerModuleExcpetion("ping tool and non ICMP protocol selected.")

        server_cls = self.traffic_classes.get(traffic_tool).get("server")
        client_cls = self.traffic_classes.get(traffic_tool).get("client")

        server_args, client_args = self._prepare_traffic_args(traffic_tool, protocol)

        server = server_cls(**server_args)
        clients = [client_cls(**client_args[client_index]) for client_index in range(len(self.clients_connections))]
        return Stream(clients, server, port=server.port if hasattr(server, "port") else None)

    def _prepare_traffic_args(
        self, traffic_tool: TrafficTools, protocol: Protocols
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        Prepare arguments for client and server traffic constructors.

        :param traffic_tool: Object of enum representing tested traffic tool to be used
        :param protocol: Object of enum representing protocol to be used
        :return: Dict of args for traffic server and list of dicts of args for traffic clients
        :raises StressTrafficModuleException: When specified traffic_tool is not supported
        """
        server_args = {}
        client_args = []
        if traffic_tool == TrafficTools.PING:
            for client_index in range(len(self.clients_connections)):
                client_args.append(
                    {
                        "connection": self.clients_connections[client_index],
                        "dst_ip": self.dst_ip,
                        "packet_size": self._random_packet_size,
                    }
                )
        elif traffic_tool in [TrafficTools.IPERF2, TrafficTools.IPERF3]:
            port = self._next_port
            server_args = {
                "connection": self.sut_connection,
                "port": port,
                "bind_address": self.dst_ip,
            }
            for client_index in range(len(self.clients_connections)):
                client_args.append(
                    {
                        "connection": self.clients_connections[client_index],
                        "dest_ip": self.dst_ip,
                        "port": port,
                        "bind_address": self.src_ips[client_index],
                        "duplex": True,
                        "time": 0,
                        "udp": protocol == Protocols.UDP,
                        "length": self._random_packet_size,
                    }
                )
                if traffic_tool == TrafficTools.IPERF3:
                    client_args[client_index]["sctp"] = protocol == Protocols.SCTP
        elif traffic_tool == TrafficTools.NETPERF_OMNI:
            port = self._next_port
            packet_size = self._random_packet_size
            server_args = {
                "connection": self.sut_connection,
                "bind_address": self.dst_ip,
                "port": port,
            }
            for client_index in range(len(self.clients_connections)):
                client_args.append(
                    {
                        "connection": self.clients_connections[client_index],
                        "port": port,
                        "dest_ip": self.dst_ip,
                        "src_ip": self.src_ips[client_index],
                        "duration": 0,
                        "protocol": protocol,
                        "send_size": packet_size,
                        "receive_size": packet_size,
                    }
                )
        else:
            raise StressTrafficManagerModuleExcpetion(f"Selected traffic tool: {traffic_tool.value} not supported yet.")
        return server_args, client_args

    @property
    def _random_duration(self) -> int:
        """Generate random duration time based on the given boundaries."""
        return random.randint(self.min_dur, self.max_dur)

    @property
    def _random_protocol(self) -> Protocols:
        """Randomly select a protocol from the given list."""
        return random.choice(self.protocols)

    @property
    def _random_packet_size(self) -> int:
        """Generate random packet size based on the given boundaries."""
        return random.randint(self.min_size, self.max_size)

    @property
    def _paused(self) -> bool:
        """Get the value of property indicating paused/unpaused state of the StressTrafficManager."""
        return self.__paused

    @_paused.setter
    def _paused(self, state: bool) -> None:
        """
        Set the _paused state of the StressTrafficManager.

        :param state: Bool state to be set
        :raises StressTrafficManagerModuleException: To avoid complications when trying to pause/unpause paused/unpaused
                                                     StressTrafficManager
        """
        if self.__paused != state:
            self.__paused = state
        else:
            raise StressTrafficManagerModuleExcpetion(
                "Cannot pause/unpause - traffic manager already in expected state."
            )

    @property
    def _next_port(self) -> int:
        """
        Get the current port number and raise the value by 1 for future usage.

        :return: Port number to be used for traffics
        """
        port, self._port = self._port, self._port + 1
        return port
