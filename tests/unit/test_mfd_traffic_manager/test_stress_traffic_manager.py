# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

import re
import concurrent.futures
from unittest import mock

import pytest
from mfd_common_libs import log_levels
from mfd_connect import RPyCConnection

from mfd_traffic_manager import StressTrafficManager, Protocols, TrafficTools, Stream
from mfd_traffic_manager.exceptions import StressTrafficManagerModuleExcpetion


PingClientTraffic = mock.Mock()
PingServerTraffic = mock.Mock()
NetperfClientTraffic = mock.Mock()
NetperfClientOmniTraffic = mock.Mock()
NetperfServerTraffic = mock.Mock()
Iperf2ClientTraffic = mock.Mock()
Iperf2ServerTraffic = mock.Mock()


TRAFFIC_CLASSES = {
    TrafficTools.PING: {"client": PingClientTraffic, "server": PingServerTraffic},
    TrafficTools.IPERF2: {"client": Iperf2ClientTraffic, "server": Iperf2ServerTraffic},
    TrafficTools.NETPERF_OMNI: {"client": NetperfClientOmniTraffic, "server": NetperfServerTraffic},
}


class TestStressTrafficManager:
    @pytest.fixture(scope="class")
    def server_connection(self):
        yield mock.create_autospec(RPyCConnection)

    @pytest.fixture(scope="class")
    def client1_connection(self):
        yield mock.create_autospec(RPyCConnection)

    @pytest.fixture(scope="class")
    def client2_connection(self):
        yield mock.create_autospec(RPyCConnection)

    @pytest.fixture()
    def manager(self, server_connection, client1_connection, client2_connection):
        yield StressTrafficManager(
            sut_connection=server_connection,
            src_ips=["1.2.1.1", "1.1.1.1"],
            dst_ip="1.1.1.1",
            clients_connections=[client1_connection, client2_connection],
            traffic_classes=TRAFFIC_CLASSES,
            start_port=1,
            num_streams=4,
            min_dur=20,
            max_dur=25,
            min_size=3,
            max_size=200,
            protocols=[Protocols.UDP, Protocols.TCP, Protocols.ICMP],
            traffic_tools=[TrafficTools.NETPERF, TrafficTools.IPERF2],
            comm_type=None,
        )

    @pytest.fixture(scope="class")
    def class_manager(self, manager):
        yield manager

    def test__create_random_stream_icmp_not_ping(self, manager, mocker):
        mocker.patch("mfd_traffic_manager.stress_traffic_manager.random.choice", return_value=Protocols.ICMP)
        with pytest.raises(
            StressTrafficManagerModuleExcpetion, match="ICMP protocol selected but ping not in allowed tools."
        ):
            manager._create_random_stream()

    def test__create_random_stream_icmp(self, manager, mocker):
        mocker.patch("mfd_traffic_manager.stress_traffic_manager.random.choice", return_value=Protocols.ICMP)
        PingServerTraffic.return_value.port = None
        manager.traffic_tools = [TrafficTools.PING]
        stream = manager._create_random_stream()
        expected_clients = [PingClientTraffic(), PingClientTraffic()]
        expected_server = PingServerTraffic()
        assert stream.clients == expected_clients and stream.server == expected_server

    def test__create_random_stream_netperf(self, manager, mocker):
        mocker.patch(
            "mfd_traffic_manager.stress_traffic_manager.random.choice",
            side_effect=[Protocols.TCP, TrafficTools.NETPERF_OMNI],
        )
        mocker.patch("mfd_traffic_manager.stream.reserve_port")
        stream = manager._create_random_stream()
        expected_clients = [NetperfClientOmniTraffic(), NetperfClientOmniTraffic()]
        expected_server = NetperfServerTraffic()
        assert stream.clients == expected_clients and stream.server == expected_server

    def test__create_random_stream_ping_non_icmp(self, manager, mocker):
        mocker.patch(
            "mfd_traffic_manager.stress_traffic_manager.random.choice",
            side_effect=[Protocols.TCP, TrafficTools.PING],
        )
        manager.traffic_tools = [TrafficTools.PING]
        with pytest.raises(StressTrafficManagerModuleExcpetion, match="ping tool and non ICMP protocol selected."):
            manager._create_random_stream()

    def test__create_random_stream_sctp_mismatch(self, manager, mocker):
        mocker.patch(
            "mfd_traffic_manager.stress_traffic_manager.random.choice",
            side_effect=[Protocols.SCTP, TrafficTools.PING],
        )
        manager.traffic_tools = [TrafficTools.PING]
        with pytest.raises(
            StressTrafficManagerModuleExcpetion, match="SCTP protocol passed but no SCTP supporting tool allowed."
        ):
            manager._create_random_stream()

    def test__next_port(self, manager):
        assert manager._next_port == 1
        assert manager._next_port == 2

    def test__paused(self, manager):
        manager._paused = True
        assert manager._paused is True
        manager._paused = False
        assert manager._paused is False
        with pytest.raises(
            StressTrafficManagerModuleExcpetion,
            match="Cannot pause/unpause - traffic manager already in expected state.",
        ):
            manager._paused = False

    def test__random_packet_size(self, manager):
        assert manager._random_packet_size in range(manager.min_size, manager.max_size + 1)

    def test__random_protocol(self, manager):
        assert manager._random_protocol in manager.protocols

    def test__random_duration(self, manager):
        assert manager._random_duration in range(manager.min_dur, manager.max_dur + 1)

    def test__prepare_traffic_args_iperf(self, manager, mocker):
        mocker.patch("mfd_traffic_manager.stress_traffic_manager.random.randint", return_value=5)
        server_args, client_args = manager._prepare_traffic_args(TrafficTools.IPERF2, Protocols.TCP)
        assert server_args == {
            "connection": manager.sut_connection,
            "bind_address": manager.dst_ip,
            "port": 1,
        }
        assert client_args == [
            {
                "connection": manager.clients_connections[0],
                "dest_ip": "1.1.1.1",
                "port": 1,
                "bind_address": "1.2.1.1",
                "duplex": True,
                "time": 0,
                "udp": False,
                "length": 5,
            },
            {
                "connection": manager.clients_connections[1],
                "dest_ip": "1.1.1.1",
                "port": 1,
                "bind_address": "1.1.1.1",
                "duplex": True,
                "time": 0,
                "udp": False,
                "length": 5,
            },
        ]

    def test__prepare_traffic_args_netperf(self, manager, mocker):
        mocker.patch("mfd_traffic_manager.stress_traffic_manager.random.randint", return_value=5)
        server_args, client_args = manager._prepare_traffic_args(TrafficTools.NETPERF_OMNI, Protocols.TCP)
        assert server_args == {
            "connection": manager.sut_connection,
            "bind_address": manager.dst_ip,
            "port": 1,
        }
        assert client_args == [
            {
                "connection": manager.clients_connections[0],
                "dest_ip": "1.1.1.1",
                "port": 1,
                "src_ip": "1.2.1.1",
                "duration": 0,
                "protocol": Protocols.TCP,
                "send_size": 5,
                "receive_size": 5,
            },
            {
                "connection": manager.clients_connections[1],
                "dest_ip": "1.1.1.1",
                "port": 1,
                "src_ip": "1.1.1.1",
                "duration": 0,
                "protocol": Protocols.TCP,
                "send_size": 5,
                "receive_size": 5,
            },
        ]

    def test__prepare_traffic_args_ping(self, manager, mocker):
        mocker.patch("mfd_traffic_manager.stress_traffic_manager.random.randint", return_value=5)
        server_args, client_args = manager._prepare_traffic_args(TrafficTools.PING, Protocols.TCP)
        assert server_args == {}
        assert client_args == [
            {
                "connection": manager.clients_connections[0],
                "dst_ip": "1.1.1.1",
                "packet_size": 5,
            },
            {
                "connection": manager.clients_connections[1],
                "dst_ip": "1.1.1.1",
                "packet_size": 5,
            },
        ]

    def test__prepare_traffic_args_incorrect_traffic(self, manager):
        with pytest.raises(
            StressTrafficManagerModuleExcpetion, match="Selected traffic tool: netperf not supported yet."
        ):
            manager._prepare_traffic_args(TrafficTools.NETPERF, Protocols.TCP)

    def test_stop_raises_not_implemented_error(self, manager):
        with pytest.raises(
            NotImplementedError, match=re.escape("stop() method not applicable to stress traffic manager.")
        ):
            manager.stop("stream_name")

    def test_start_raises_not_implemented_error(self, manager):
        with pytest.raises(
            NotImplementedError, match=re.escape("start() method not applicable to stress traffic manager.")
        ):
            manager.start("stream_name")

    def test_run_raises_not_implemented_error(self, manager):
        with pytest.raises(
            NotImplementedError, match=re.escape("run() method not applicable to stress traffic manager.")
        ):
            manager.run("stream_name", 10)

    def test_run_all_raises_not_implemented_error(self, manager):
        with pytest.raises(
            NotImplementedError, match=re.escape("run_all() method not applicable to stress traffic manager.")
        ):
            manager.run_all(10)

    def test_start_all(self, manager, mocker):
        mocker.patch("mfd_traffic_manager.stress_traffic_manager.random.randint", return_value=5)
        manager._create_random_stream = mocker.create_autospec(manager._create_random_stream)
        manager.executor = mocker.create_autospec(manager.executor)
        streams = [mocker.create_autospec(Stream), mocker.create_autospec(Stream)]
        manager.num_streams = len(streams)
        manager._create_random_stream.side_effect = streams
        calls = []
        for stream in streams:
            calls.append(mocker.call(stream.run, 5))
        calls.append(mocker.call(manager._control_streams))
        manager.start_all()
        manager.executor.submit.assert_has_calls(calls, any_order=True)

    def test_stop_all(self, manager, mocker):
        mocker.patch("mfd_traffic_manager.stress_traffic_manager.time.sleep")
        manager.executor = mocker.create_autospec(manager.executor)
        manager._results_ready = True
        manager.event = mocker.create_autospec(manager.event)
        manager.stop_all()
        manager.event.set.assert_called_once()
        manager.executor.shutdown.assert_called_once_with(wait=True, cancel_futures=True)

    def test_pause_all(self, manager, mocker):
        mocker.patch("mfd_traffic_manager.stress_traffic_manager.time.sleep")
        manager.__paused = False
        manager._results_ready = True
        manager.event = mocker.create_autospec(manager.event)
        manager.pause_all()
        manager.event.set.assert_called_once()
        assert manager._paused is True

    def test_pause_all_duration(self, manager, mocker):
        mocker_sleep = mocker.patch("mfd_traffic_manager.stress_traffic_manager.time.sleep")
        manager.__paused = False
        manager._results_ready = True
        manager.event = mocker.create_autospec(manager.event)
        manager.start_all = mocker.create_autospec(manager.start_all)
        manager.pause_all(duration=5685)
        manager.event.set.assert_called_once()
        mocker_sleep.assert_called_once_with(5685)
        manager.start_all.assert_called_once()
        assert manager._paused is False

    def test_pause_all_already_paused(self, manager):
        manager._paused = True
        with pytest.raises(StressTrafficManagerModuleExcpetion, match="Stress Traffic Manager is already paused."):
            manager.pause_all()

    def test_resume_all(self, manager, mocker):
        manager._paused = True
        manager.num_streams = 2
        manager._create_random_stream = mocker.create_autospec(manager._create_random_stream)
        manager.event = mocker.create_autospec(manager.event)
        manager.start_all = mocker.create_autospec(manager.start_all)
        manager.resume_all()
        manager.event.clear.assert_called_once()
        assert manager._paused is False
        manager.start_all.assert_called_once()

    def test_resume_all_not_paused(self, manager):
        manager.__paused = False
        with pytest.raises(StressTrafficManagerModuleExcpetion, match="Stress Traffic Manager is already running."):
            manager.resume_all()

    def test__control_streams_new(self, manager, mocker, caplog):
        caplog.set_level(level=log_levels.MODULE_DEBUG)
        mocked_stream_1 = mocker.create_autospec(Stream)
        mocked_stream_2 = mocker.create_autospec(Stream)
        manager.event = mocker.create_autospec(manager.event)
        mocker.patch("mfd_traffic_manager.stress_traffic_manager.time.sleep")
        manager.event.is_set.side_effect = [False, True]
        future1 = mocker.create_autospec(concurrent.futures.Future)
        future2 = mocker.create_autospec(concurrent.futures.Future)
        manager.futures = {future1: mocked_stream_1, future2: mocked_stream_2}

        future1.done.return_value = True
        future2.done.return_value = False

        new_mocked_stream = mocker.create_autospec(Stream)
        manager._create_random_stream = mocker.Mock(return_value=new_mocked_stream)

        mocker.patch("mfd_traffic_manager.stress_traffic_manager.random.randint", return_value=5)

        manager.executor = mocker.create_autospec(manager.executor)
        manager.stop_all = mocker.create_autospec(manager.stop_all)

        mocker.patch("mfd_traffic_manager.stress_traffic_manager.event.is_set", return_value=True)
        stop_all_mock = mocker.patch("mfd_traffic_manager.TrafficManager.stop_all")

        manager.streams = [mocked_stream_1, mocked_stream_2]

        manager._control_streams()

        manager.executor.submit.assert_called_once_with(new_mocked_stream.run, 5)

        assert "Completed stream detected. Starting new one with duration: 5 s" in caplog.messages
        stop_all_mock.assert_called_once()
        assert all(stream in manager.streams for stream in [mocked_stream_1, mocked_stream_2, new_mocked_stream])
