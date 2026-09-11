#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Fixture containing abstract classes and concrete subtypes."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Shape(ABC):
    """Abstract base class representing a geometric shape."""

    @abstractmethod
    def area(self) -> float:
        """Calculate the area of the shape.

        Returns:
            The calculated area as a float.
        """


class Circle(Shape):
    """Concrete circle implementing Shape."""

    def __init__(self, radius: float) -> None:
        """Initialize circle with radius.

        Args:
            radius: The circle radius.
        """
        self.radius = radius

    def area(self) -> float:
        """Calculate area of circle.

        Returns:
            The area of the circle.
        """
        return 3.14159 * self.radius * self.radius


class Rectangle(Shape):
    """Concrete rectangle implementing Shape."""

    def __init__(self, width: float, height: float) -> None:
        """Initialize rectangle with width and height.

        Args:
            width: The rectangle width.
            height: The rectangle height.
        """
        self.width = width
        self.height = height

    def area(self) -> float:
        """Calculate area of rectangle.

        Returns:
            The area of the rectangle.
        """
        return self.width * self.height


def calculate_area(shape: Shape) -> float:
    """Calculate area of any shape.

    Args:
        shape: The shape to calculate the area for.

    Returns:
        The shape's area.
    """
    return shape.area()


class Animal(ABC):
    """Abstract animal."""

    @abstractmethod
    def sound(self) -> str:
        """Return animal sound.

        Returns:
            The animal sound.
        """


class Bird(Animal):
    """Intermediate abstract bird class."""

    @abstractmethod
    def wingspan(self) -> float:
        """Return wingspan.

        Returns:
            The wingspan.
        """


class Penguin(Bird):
    """Concrete penguin class."""

    def __init__(self, name: str) -> None:
        """Initialize penguin.

        Args:
            name: The penguin's name.
        """
        self.name = name

    def sound(self) -> str:
        """Return penguin sound.

        Returns:
            The sound.
        """
        return "honk"

    def wingspan(self) -> float:
        """Return wingspan.

        Returns:
            The wingspan.
        """
        return 0.5


def describe_animal(animal: Animal) -> str:
    """Describe an animal by its sound.

    Args:
        animal: The animal to describe.

    Returns:
        Description string.
    """
    return animal.sound()
