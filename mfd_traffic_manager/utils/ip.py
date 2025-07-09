# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Package for ip utilities."""

import atexit
import logging
import time
from dataclasses import dataclass

from mfd_common_libs import log_levels, TimeoutCounter
from mfd_connect import AsyncConnection
from mfd_connect.process import RemoteProcess
from mfd_typing import OSName

from mfd_traffic_manager.exceptions import TrafficManagerModuleException

logger = logging.getLogger(__name__)

# 65 is some high file descriptor number, assumed not used by anyone.
reserve_command_template = {
    OSName.WINDOWS: (
        "powershell -NoExit $Address = [system.net.IPAddress]::Parse('{ip_address}'); "
        "$UdpObject = New-Object System.Net.Sockets.UdpClient({port})"
    ),
    OSName.LINUX: "bash -c 'exec 65</dev/udp/{ip_address}/{port};read -n 1'",
    OSName.ESXI: "nc -l {port}",
    OSName.FREEBSD: "bash -c 'exec 65</dev/udp/{ip_address}/{port};read -n 1'",
}
check_port_command_template = {
    OSName.ESXI: "esxcli network ip connection list | grep ':{port} '",
    OSName.LINUX: "netstat -na | grep ':{port} '",
    OSName.WINDOWS: 'netstat -na | findstr /c:":{port} "',
    OSName.FREEBSD: "netstat -na | grep '.{port} '",
}


@dataclass
class PortReservation:
    """Class for reserved port."""

    port: int
    connection: "AsyncConnection"
    process: "RemoteProcess"

    def __post_init__(self):
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        """Clean up port reservation on the end of python."""
        if self.process.running:
            logger.log(level=log_levels.MODULE_DEBUG, msg="Cleaning up port reservation.")
            self.process.kill()


def check_if_port_is_free(connection: "AsyncConnection", port: int) -> bool:
    """
    Check if passed port, if free to use.

    Free port means not used or with TIME_WAIT status.

    :param connection: Connection object
    :param port: Port value
    :return: Boolean status as information if port is free
    """
    os_name = connection.get_os_name()
    logger.log(level=log_levels.MODULE_DEBUG, msg=f"Checking if port {port} is free")
    check_port_result = connection.execute_command(
        check_port_command_template[os_name].format(port=port),
        shell=True,
        expected_return_codes=[0, 1],
    )
    found_ports = check_port_result.stdout.splitlines()
    status = check_port_result.return_code != 0 or all("TIME_WAIT" in port for port in found_ports)
    logger.log(level=log_levels.MODULE_DEBUG, msg=f"Port {port} is {'not ' if not status else ''}free")
    return status


def reserve_port(connection: "AsyncConnection", port: int, find_port: bool = True, count: int = 10) -> PortReservation:
    """
    Reserve given port number.

    Reservation means open UDP socket in system.

    :param connection: Connection object
    :param port: Port value
    :param find_port: Flag to find first available port,
    :param count: Value of how many tries to find next free port

    :return: Object representing reservation of port
    """
    os_name = connection.get_os_name()
    if not check_if_port_is_free(connection, port):
        if find_port:
            port = find_free_port(connection, port, count=count)
        else:
            raise TrafficManagerModuleException(f"Port {port} is not free to reserve.")
    logger.log(level=log_levels.MODULE_DEBUG, msg=f"Reserving port {port}.")
    reserve_process = connection.start_process(
        reserve_command_template[os_name].format(port=port, ip_address="127.0.0.1"),
        shell=True,
        enable_input=True,
        stderr_to_stdout=True,
    )
    timeout = TimeoutCounter(10)
    while not timeout:
        is_port_free = check_if_port_is_free(connection, port)
        if not is_port_free:
            logger.log(level=log_levels.MODULE_DEBUG, msg="Expected that port is not free")
            logger.log(level=log_levels.MODULE_DEBUG, msg="Reserved port")
            return PortReservation(connection=connection, port=port, process=reserve_process)
        time.sleep(1)
    else:
        if reserve_process.running:
            reserve_process.stop()
        logger.log(level=log_levels.MODULE_DEBUG, msg=reserve_process.stdout_text)
        raise TrafficManagerModuleException(f"Cannot reserve port {port}, it is already in use.")


def find_free_port(connection: "AsyncConnection", port: int, count: int = 10) -> int:
    """
    Find next free port for reservation.

    :param connection: Connection object.
    :param port: Starting port number
    :param count: Value of how many tries to find next free port
    :return: value
    """
    for _ in range(count):
        port += 1
        if check_if_port_is_free(connection, port):
            break
    else:
        raise TrafficManagerModuleException("Not found free port to reserve.")
    return port


def unreserve_port(reservation: PortReservation) -> None:
    """
    Unreserve port.

    :param reservation: Reservation object
    """
    if reservation.process.running:
        reservation.process.stop()
    time.sleep(5)  # wait time to cleanup socket
    is_port_free = check_if_port_is_free(reservation.connection, reservation.port)
    if not is_port_free:
        raise TrafficManagerModuleException(f"Failed to unreserve port {reservation.port}, it is still running.")
    logger.log(level=log_levels.MODULE_DEBUG, msg="Unreserved port")
