"""
Generic registry base class for managing registered items.

Provides a common interface for all registry types in NanoAgent.
"""

from typing import Generic, TypeVar

T = TypeVar("T")


class BaseRegistry(Generic[T]):
    """
    Abstract base for all registries.

    Provides common operations: register, unregister, get, list, contains, len.
    Subclasses can add domain-specific methods.
    """

    def __init__(self):
        self._items: dict[str, T] = {}

    def register(self, item: T, name: str | None = None) -> None:
        """
        Register an item.

        Args:
            item: The item to register
            name: Optional name override. If not provided, uses item's 'name' attribute.

        Raises:
            ValueError: If name cannot be determined
        """
        key = name or getattr(item, "name", None)
        if key is None:
            raise ValueError("Item must have a 'name' attribute or name must be provided")
        self._items[key] = item

    def unregister(self, name: str) -> bool:
        """
        Unregister an item by name.

        Args:
            name: Name of the item to unregister

        Returns:
            True if item was unregistered, False if not found
        """
        if name in self._items:
            del self._items[name]
            return True
        return False

    def get(self, name: str) -> T | None:
        """
        Get an item by name.

        Args:
            name: Name of the item

        Returns:
            The item or None if not found
        """
        return self._items.get(name)

    def list_all(self) -> list[str]:
        """
        List all registered item names.

        Returns:
            List of registered names
        """
        return list(self._items.keys())

    def clear(self) -> None:
        """Clear all registered items."""
        self._items.clear()

    def __contains__(self, name: str) -> bool:
        """Check if an item is registered."""
        return name in self._items

    def __len__(self) -> int:
        """Return number of registered items."""
        return len(self._items)

    def __bool__(self) -> bool:
        """Registry is always truthy, even if empty."""
        return True

    def __iter__(self):
        """Iterate over registered items."""
        return iter(self._items.values())
