# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

from typing import Dict, Callable, Any

import pytest

from mfd_traffic_manager.base import Traffic
from mfd_traffic_manager.stream import Stream


def validate(results, *, minimum: int) -> bool:
    return minimum > 0


criteria = {validate: {"a": 1}}
server_criteria = {validate: {"b": 1}}
client_criteria = {validate: {"c": 1}}


class DummyServer(Traffic):
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def run(self, duration: int) -> None:
        pass

    def validate(self, validation_criteria: Dict[Callable, Dict[str, Any]] = None) -> bool:
        pass


class DummyClient(Traffic):
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def run(self, duration: int) -> None:
        pass

    def validate(self, validation_criteria: Dict[Callable, Dict[str, Any]] = None) -> bool:
        pass


class TestStream:
    @pytest.fixture(scope="class")
    def stream(self):
        server = DummyServer()
        client = DummyClient()
        yield Stream(clients=[client], server=server)

    @pytest.mark.parametrize(
        "common_validation_criteria, server_validation_criteria, clients_validation_criteria",
        [
            (criteria, criteria, criteria),
            (criteria, criteria, None),
            (criteria, None, criteria),
        ],
        ids=["common+server+client", "common+server", "common+client"],
    )
    def test__verify_validation_criteria_invalid(
        self, stream, common_validation_criteria, server_validation_criteria, clients_validation_criteria
    ):
        with pytest.raises(ValueError):
            stream._verify_validation_criteria(
                common_validation_criteria=common_validation_criteria,
                server_validation_criteria=server_validation_criteria,
                clients_validation_criteria=clients_validation_criteria,
            )

    @pytest.mark.parametrize(
        "common_validation_criteria, server_validation_criteria, clients_validation_criteria",
        [
            (criteria, None, None),
            (None, criteria, None),
            (None, None, criteria),
            (None, criteria, criteria),
        ],
        ids=["common", "server", "client", "server+client"],
    )
    def test__verify_validation_criteria(
        self, stream, common_validation_criteria, server_validation_criteria, clients_validation_criteria
    ):
        stream._verify_validation_criteria(
            common_validation_criteria=common_validation_criteria,
            server_validation_criteria=server_validation_criteria,
            clients_validation_criteria=clients_validation_criteria,
        )

    @pytest.mark.parametrize(
        "common_validation_criteria, server_validation_criteria, clients_validation_criteria, "
        "expected_server_criteria, expected_client_criteria",
        [
            (criteria, None, None, criteria, criteria),
            (None, criteria, None, criteria, {lambda r, x: x: {"x": True}}),
            (None, None, criteria, {lambda r, x: x: {"x": True}}, criteria),
            (None, server_criteria, client_criteria, server_criteria, client_criteria),
        ],
        ids=["common", "server", "client", "server+client"],
    )
    def test__set_default_criteria(
        self,
        stream,
        common_validation_criteria,
        server_validation_criteria,
        clients_validation_criteria,
        expected_server_criteria,
        expected_client_criteria,
    ):
        server, client = stream._set_default_criteria(
            common_validation_criteria, server_validation_criteria, clients_validation_criteria
        )
        assert str(client.values()) == str(expected_client_criteria.values()) and str(server.values()) == str(
            expected_server_criteria.values()
        )

    def test_validate(self, stream, mocker):
        stream.server.validate = mocker.create_autospec(DummyServer.validate)
        stream.clients[0].validate = mocker.create_autospec(DummyClient.validate)
        stream.validate(server_validation_criteria=server_criteria, clients_validation_criteria=client_criteria)
        stream.server.validate.assert_called_once_with(server_criteria)
        stream.clients[0].validate.assert_called_once_with(client_criteria)

    def test_run(self, stream, mocker):
        stream.server.run = mocker.Mock()
        stream.server.stop = mocker.Mock()
        stream.clients[0].run = mocker.Mock()
        stream.run(duration=1)
        stream.server.run.assert_called_once_with(1)
        stream.server.stop.assert_called_once()
        stream.clients[0].run.assert_called_once()
