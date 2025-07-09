# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

from typing import Dict, Callable, Any

import pytest

from mfd_traffic_manager import SingleHostStream
from mfd_traffic_manager.base import Traffic


def validate(results, *, minimum: int) -> bool:
    return minimum > 0


criteria = {validate: {"a": 1}}
default = {validate: {"x": True}}


class DummyServer(Traffic):
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def run(self, duration: int) -> None:
        pass

    def validate(self, validation_criteria: Dict[Callable, Dict[str, Any]] = None) -> bool:
        pass


class TestSingleHostStream:
    @pytest.fixture(scope="class")
    def stream(self) -> SingleHostStream:
        server = DummyServer()
        yield SingleHostStream(server=server)

    @pytest.mark.parametrize(
        "common_validation_criteria, expected_server_criteria",
        [(criteria, criteria), (None, default)],
        ids=["default", "passed"],
    )
    def test__set_default_criteria(
        self,
        stream,
        common_validation_criteria,
        expected_server_criteria,
    ):
        server = stream._set_default_criteria(common_validation_criteria)
        assert str(server.values()) == str(expected_server_criteria.values())

    def test_validate(self, stream, mocker):
        stream.server.validate = mocker.create_autospec(DummyServer.validate)
        stream.validate(criteria)
        stream.server.validate.assert_called_once_with(criteria)

    def test_run(self, stream, mocker):
        stream.server.run = mocker.Mock()
        stream.run(duration=1)
        stream.server.run.assert_called_once_with(1)

    def test_start(self, stream, mocker):
        stream.server.start = mocker.Mock()
        stream.start()
        stream.server.start.assert_called_once()

    def test_stop(self, stream, mocker):
        stream.server.stop = mocker.Mock()
        stream.stop()
        stream.server.stop.assert_called_once()
