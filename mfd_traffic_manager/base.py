# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for base."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Callable, Any


class Traffic(ABC):
    """Base class for all types of traffic."""

    @abstractmethod
    def start(self) -> None:
        """
        Start traffic.

        :return: None
        """
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """
        Stop traffic.

        :return: None
        """
        raise NotImplementedError

    @abstractmethod
    def run(self, duration: int) -> None:
        """
        Run traffic for specified duration.

        :param duration: duration of traffic in seconds
        :return: None
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None) -> bool:
        """
        Validate traffic by specified criteria.

        :param validation_criteria: criteria by which traffic should be validated
        :return: True if traffic is correct according to criteria, False otherwise
        """
        raise NotImplementedError

    def _validate(
        self,
        results: List,
        validation_criteria: Optional[Dict[Callable, Dict[str, Any]]] = None,
    ) -> bool:
        validation_criteria = (
            {lambda r, x: x: {"x": True}} if not validation_criteria else validation_criteria
        )  # default criteria which pass always
        return all(function(results, **params) for function, params in validation_criteria.items())

    @property
    def started(self) -> bool:
        """Check if _process attribute is available after calling start() method."""
        return hasattr(self, "_process")

    @property
    def running(self) -> bool:
        """Check if process is running."""
        return self._process.running
