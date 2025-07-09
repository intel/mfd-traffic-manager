# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

import pytest
from unittest.mock import patch, Mock

from mfd_typing import OSName

from mfd_traffic_manager import check_if_port_is_free, reserve_port, unreserve_port
from mfd_traffic_manager.exceptions import TrafficManagerModuleException
from mfd_traffic_manager.utils import PortReservation, find_free_port


class TestIpUtils:
    def test_check_if_port_is_free(self, mocker):
        mock_conn = mocker.patch("mfd_traffic_manager.utils.ip.AsyncConnection")
        mock_conn.get_os_name.return_value = OSName.LINUX
        mock_conn.execute_command.return_value.return_code = 1

        # Now the function should say some random port is free
        assert check_if_port_is_free(mock_conn, 12345) is True

    def test_reserve_port(self, mocker):
        mock_check_if_port_is_free = mocker.patch("mfd_traffic_manager.utils.ip.check_if_port_is_free")
        mocker.patch("mfd_traffic_manager.utils.ip.time.sleep")
        timeout_mocker = mocker.patch("mfd_traffic_manager.utils.ip.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = False
        mock_conn = mocker.patch("mfd_traffic_manager.utils.ip.AsyncConnection")
        mock_conn.get_os_name.return_value = OSName.LINUX
        mock_check_if_port_is_free.side_effect = [True, False]
        # Now we should be able to reserve port 12345
        reserve = reserve_port(mock_conn, 12345)
        mock_conn.start_process.assert_called_once_with(
            "bash -c 'exec 65</dev/udp/127.0.0.1/12345;read -n 1'",
            shell=True,
            enable_input=True,
            stderr_to_stdout=True,
        )
        assert isinstance(reserve, PortReservation)
        assert reserve.port == 12345

    def test_reserve_port_when_port_not_free(self, mocker):
        mock_check_if_port_is_free = mocker.patch("mfd_traffic_manager.utils.ip.check_if_port_is_free")
        timeout_mocker = mocker.patch("mfd_traffic_manager.utils.ip.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = False
        mocker.patch("mfd_traffic_manager.utils.ip.time.sleep")
        mock_conn = mocker.patch("mfd_traffic_manager.utils.ip.AsyncConnection")
        mock_conn.get_os_name.return_value = OSName.LINUX
        mock_check_if_port_is_free.return_value = False

        with pytest.raises(TrafficManagerModuleException):
            reserve_port(mock_conn, 12345, find_port=False)

        mock_conn.start_process.assert_not_called()

    def test_reserve_port_when_check_if_port_is_free_is_false(self, mocker):
        mocker.patch("mfd_traffic_manager.utils.ip.time.sleep")
        timeout_mocker = mocker.patch("mfd_traffic_manager.utils.ip.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = True
        mock_conn = mocker.patch("mfd_traffic_manager.utils.ip.AsyncConnection")

        mock_conn.get_os_name.return_value = OSName.LINUX
        netstat_output_in_use = "tcp        0      0 127.0.0.1:12345        0.0.0.0:*               LISTEN      "
        mock_conn.execute_command.return_value.stdout = netstat_output_in_use

        with pytest.raises(TrafficManagerModuleException):
            reserve_port(mock_conn, 12345)

    def test_reserve_port_when_find_free_port_is_false(self, mocker):
        mocker.patch("mfd_traffic_manager.utils.ip.time.sleep")
        timeout_mocker = mocker.patch("mfd_traffic_manager.utils.ip.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = True
        mock_conn = mocker.patch("mfd_traffic_manager.utils.ip.AsyncConnection")
        mock_conn.get_os_name.return_value = OSName.LINUX
        netstat_output_in_use = "tcp        0      0 127.0.0.1:12345        0.0.0.0:*               LISTEN      "
        mock_conn.execute_command.return_value.stdout = netstat_output_in_use

        with patch("mfd_traffic_manager.utils.ip.find_free_port", return_value=False):
            with pytest.raises(TrafficManagerModuleException):
                reserve_port(mock_conn, 12345, find_port=False)

    def test_reserve_port_when_find_free_port_is_true(self, mocker):
        timeout_mocker = mocker.patch("mfd_traffic_manager.utils.ip.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = False
        find_free_port_mock = mocker.patch("mfd_traffic_manager.utils.ip.find_free_port")
        mock_check_if_port_is_free = mocker.patch("mfd_traffic_manager.utils.ip.check_if_port_is_free")
        mocker.patch("mfd_traffic_manager.utils.ip.time.sleep")
        mock_conn = mocker.patch("mfd_traffic_manager.utils.ip.AsyncConnection")
        mock_conn.get_os_name.return_value = OSName.LINUX
        mock_check_if_port_is_free.return_value = False
        find_free_port_mock.return_value = 12346
        # Now we should be able to reserve port 12345
        reserve = reserve_port(mock_conn, 12345, find_port=True)
        mock_conn.start_process.assert_called_once_with(
            "bash -c 'exec 65</dev/udp/127.0.0.1/12346;read -n 1'",
            shell=True,
            enable_input=True,
            stderr_to_stdout=True,
        )
        assert isinstance(reserve, PortReservation)
        assert reserve.port == 12346
        find_free_port_mock.assert_called_once_with(mock_conn, 12345, count=10)

    def test_find_free_port(self, mocker):
        mock_check_if_port_is_free = mocker.patch("mfd_traffic_manager.utils.ip.check_if_port_is_free")
        mock_check_if_port_is_free.return_value = True
        mock_conn = Mock()

        # Now we should be able to find the first free port
        assert find_free_port(mock_conn, 12345) == 12346

    def test_find_free_port_no_ports_free(self, mocker):
        mock_conn = Mock()
        mocker.patch("mfd_traffic_manager.utils.ip.check_if_port_is_free", return_value=False)

        with pytest.raises(TrafficManagerModuleException):
            find_free_port(mock_conn, 12345, count=2)

    def test_find_free_port_returns_the_same_port_when_check_if_port_is_free_is_true(self):
        with patch("mfd_traffic_manager.utils.ip.check_if_port_is_free", return_value=True):
            mock_conn = Mock()
            port = find_free_port(mock_conn, 12345)

            assert port == 12346

    def test_find_free_port_raises_exception_when_no_free_port_found(self):
        with patch("mfd_traffic_manager.utils.ip.check_if_port_is_free", return_value=False):
            mock_conn = Mock()

            with pytest.raises(TrafficManagerModuleException):
                find_free_port(mock_conn, 12345, count=1)

    def test_unreserve_port(self, mocker):
        mock_check_if_port_is_free = mocker.patch(
            "mfd_traffic_manager.utils.ip.check_if_port_is_free", return_value=False
        )
        mocker.patch("mfd_traffic_manager.utils.ip.time.sleep")

        mock_check_if_port_is_free.return_value = True
        mock_pro = Mock()
        reservation = PortReservation(port=12345, connection=Mock(), process=mock_pro)

        # We should be able to unreserve port 12345
        assert unreserve_port(reservation) is None

    def test_unreserve_port_fails_to_unreserve(self, mocker):
        mocker.patch("mfd_traffic_manager.utils.ip.check_if_port_is_free", return_value=False)
        mocker.patch("mfd_traffic_manager.utils.ip.time.sleep")

        mock_pro = Mock()
        reservation = PortReservation(port=12345, connection=Mock(), process=mock_pro)

        with pytest.raises(TrafficManagerModuleException):
            unreserve_port(reservation)

    def test_unreserve_port_when_check_if_port_is_free_is_false(self, mocker):
        mock_check_if_port_is_free = mocker.patch(
            "mfd_traffic_manager.utils.ip.check_if_port_is_free", return_value=False
        )
        mocker.patch("mfd_traffic_manager.utils.ip.time.sleep")
        mock_check_if_port_is_free.return_value = False

        with pytest.raises(TrafficManagerModuleException):
            unreserve_port(PortReservation(port=12345, connection=Mock(), process=Mock(running=False)))

    def test_unreserve_port_when_process_is_not_running(self, mocker):
        mock_reservation = mocker.patch("mfd_traffic_manager.utils.ip.PortReservation")
        check_if_port_is_free_mock = mocker.patch(
            "mfd_traffic_manager.utils.ip.check_if_port_is_free", return_value=False
        )
        mocker.patch("mfd_traffic_manager.utils.ip.time.sleep")

        mock_reservation.process.running = False
        check_if_port_is_free_mock.return_value = True
        unreserve_port(mock_reservation)

        mock_reservation.process.stop.assert_not_called()

    def test_unreserve_port_not_running(self, mocker):
        mocker.patch("mfd_traffic_manager.utils.ip.check_if_port_is_free", return_value=True)
        mocker.patch("mfd_traffic_manager.utils.ip.time.sleep")

        mock_pro = Mock(running=False)
        reservation = PortReservation(port=12345, connection=Mock(), process=mock_pro)

        unreserve_port(reservation)

        reservation.process.stop.assert_not_called()
