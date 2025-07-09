# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for exceptions."""


class TrafficManagerModuleException(Exception):
    """Handle module exceptions."""


class StressTrafficManagerModuleExcpetion(TrafficManagerModuleException):
    """Handle exceptions related to StressTrafficManager class."""
