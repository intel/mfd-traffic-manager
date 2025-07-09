# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Tests for `mfd_traffic_manager` package."""

from unittest import mock

import pytest

from mfd_traffic_manager.exceptions import TrafficManagerModuleException
from mfd_traffic_manager.manager import TrafficManager
from mfd_traffic_manager.stream import Stream


class TestMfdTrafficManager:
    @pytest.fixture()
    def manager(self):
        yield TrafficManager()

    @pytest.fixture(scope="class")
    def manager_with_added_streams(self):
        extended_manager = TrafficManager()
        stream1 = mock.create_autospec(Stream)
        stream2 = mock.create_autospec(Stream)
        stream1.name = "stream1"
        stream2.name = "stream2"
        extended_manager.add_stream(stream1)
        extended_manager.add_stream(stream2)
        yield extended_manager, stream1, stream2

    def test_start(self, manager_with_added_streams):
        manager, stream1, stream2 = manager_with_added_streams
        manager.start("stream1")
        stream1.start.assert_called_once()
        stream2.start.assert_not_called()
        stream1.reset_mock()
        stream2.reset_mock()

    def test_start_fail(self, manager_with_added_streams):
        manager, _, _ = manager_with_added_streams
        with pytest.raises(TrafficManagerModuleException, match="Not found stream with name 'stream3'"):
            manager.start("stream3")

    def test_start_all(self, manager_with_added_streams):
        manager, stream1, stream2 = manager_with_added_streams
        manager.start_all()
        stream1.start.assert_called_once()
        stream2.start.assert_called_once()
        stream1.reset_mock()
        stream2.reset_mock()

    def test_stop(self, manager_with_added_streams):
        manager, stream1, stream2 = manager_with_added_streams
        manager.stop("stream1")
        stream1.stop.assert_called_once()
        stream2.stop.assert_not_called()
        stream1.reset_mock()
        stream2.reset_mock()

    def test_stop_fail(self, manager_with_added_streams):
        manager, _, _ = manager_with_added_streams
        with pytest.raises(TrafficManagerModuleException, match="Not found stream with name 'stream3'"):
            manager.stop("stream3")

    def test_stop_all(self, manager_with_added_streams):
        manager, stream1, stream2 = manager_with_added_streams
        manager.stop_all()
        stream1.stop.assert_called_once()
        stream2.stop.assert_called_once()
        stream1.reset_mock()
        stream2.reset_mock()

    def test_validate(self, manager_with_added_streams):
        manager, stream1, stream2 = manager_with_added_streams
        manager.validate("stream1")
        stream1.validate.assert_called_once()
        stream2.validate.assert_not_called()
        stream1.reset_mock()
        stream2.reset_mock()

    def test_validate_fail(self, manager_with_added_streams):
        manager, _, _ = manager_with_added_streams
        with pytest.raises(TrafficManagerModuleException, match="Not found stream with name 'stream3'"):
            manager.validate("stream3")

    def test_validate_all(self, manager_with_added_streams):
        manager, stream1, stream2 = manager_with_added_streams
        manager.validate_all()
        stream1.validate.assert_called_once()
        stream2.validate.assert_called_once()
        stream1.reset_mock()
        stream2.reset_mock()

    def test_validate_all_fail(self, manager_with_added_streams):
        manager, stream1, stream2 = manager_with_added_streams
        stream1.validate.return_value = False
        assert manager.validate_all() is False
        stream1.reset_mock()
        stream2.reset_mock()

    def test_run(self, manager_with_added_streams):
        manager, stream1, stream2 = manager_with_added_streams
        manager.run("stream1", 1)
        stream1.run.assert_called_once_with(duration=1)
        stream2.run.assert_not_called()
        stream1.reset_mock()
        stream2.reset_mock()

    def test_run_fail(self, manager_with_added_streams):
        manager, _, _ = manager_with_added_streams
        with pytest.raises(TrafficManagerModuleException, match="Not found stream with name 'stream3'"):
            manager.run("stream3", duration=1)

    def test_run_all(self, manager_with_added_streams):
        manager, stream1, stream2 = manager_with_added_streams
        manager.run_all(1)
        stream1.run.assert_called_once_with(duration=1)
        stream2.run.assert_called_once_with(duration=1)
        stream1.reset_mock()
        stream2.reset_mock()

    def test_empty_manager(self, manager):
        assert manager.streams == []
