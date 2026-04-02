"""Custom extractor discovery and hot-loading system.

Provides :class:`ExtractorLoader` for discovering and registering custom
:class:`~kutana_core.extraction.abc.Extractor` implementations from:

- Python packages declaring ``kutana.extractors`` entry points
- Local Python source files (for development / rapid iteration)
- Programmatic registration at runtime (hot-loading without restart)

Example::

    loader = ExtractorLoader()

    # Load from an installed package's entry points
    loader.load_from_entry_points()

    # Load from a local file
    loader.load_from_file("/path/to/my_extractor.py")

    # Register a class directly
    loader.register(MyExtractor)

    # List what's loaded
    for name, cls in loader.extractors.items():
        print(name, cls)

    # Instantiate and use
    extractor = loader.create("my-extractor", api_key="...")
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any

from kutana_core.extraction.abc import Extractor

logger = logging.getLogger(__name__)

#: Entry point group name used by custom extractor packages.
ENTRY_POINT_GROUP = "kutana.extractors"


class ExtractorValidationError(Exception):
    """Raised when a custom extractor class fails validation.

    Attributes:
        cls: The class that failed validation.
        reason: Human-readable description of the failure.
    """

    def __init__(self, cls: type, reason: str) -> None:
        """Initialize with the failing class and reason."""
        self.cls = cls
        self.reason = reason
        super().__init__(f"{cls.__name__}: {reason}")


def validate_extractor(cls: type) -> None:
    """Verify that *cls* is a valid, concrete :class:`Extractor` implementation.

    Checks:
    - Is a class (not a function or other object)
    - Subclasses :class:`Extractor`
    - Is not abstract (all abstract methods are implemented)
    - ``name`` property returns a non-empty string
    - ``entity_types`` property returns a non-empty list of strings

    Args:
        cls: The class to validate.

    Raises:
        :class:`ExtractorValidationError`: If any check fails.
    """
    if not isinstance(cls, type):
        raise ExtractorValidationError(cls, "must be a class")  # type: ignore[arg-type]

    if not issubclass(cls, Extractor):
        raise ExtractorValidationError(
            cls, f"must subclass Extractor (got {cls.__bases__})"
        )

    # Check for un-implemented abstract methods
    abstract_methods = getattr(cls, "__abstractmethods__", frozenset())
    if abstract_methods:
        raise ExtractorValidationError(
            cls,
            f"has unimplemented abstract methods: {sorted(abstract_methods)}",
        )

    # Validate name and entity_types by instantiating a temporary probe
    try:
        # Use inspect to call __init__ with no required args if possible,
        # otherwise skip runtime property checks.
        init_sig = inspect.signature(cls.__init__)
        required = [
            p
            for name, p in init_sig.parameters.items()
            if name != "self"
            and p.default is inspect.Parameter.empty
            and p.kind
            not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ]
        if required:
            # Cannot instantiate without args — skip runtime property checks
            return

        instance = cls()
        name_val = instance.name
        if not isinstance(name_val, str) or not name_val.strip():
            raise ExtractorValidationError(cls, "name property must return a non-empty string")

        types_val = instance.entity_types
        if not isinstance(types_val, list) or not types_val:
            raise ExtractorValidationError(
                cls, "entity_types property must return a non-empty list"
            )
        if not all(isinstance(t, str) for t in types_val):
            raise ExtractorValidationError(
                cls, "entity_types entries must all be strings"
            )
    except ExtractorValidationError:
        raise
    except Exception as exc:
        logger.debug(
            "Skipping runtime property validation for %s (init requires args): %s",
            cls.__name__,
            exc,
        )


class ExtractorLoader:
    """Registry and loader for custom :class:`Extractor` implementations.

    Supports discovery from installed Python packages (via ``entry_points``),
    local Python source files, and direct programmatic registration.

    Hot-loading is supported: call :meth:`register`, :meth:`load_from_file`,
    or :meth:`load_from_entry_points` at any time — newly registered extractors
    are immediately available via :meth:`create` and :attr:`extractors`.

    Example::

        loader = ExtractorLoader()
        loader.load_from_entry_points()
        extractor = loader.create("compliance", anthropic_api_key="sk-...")
    """

    def __init__(self) -> None:
        """Initialize an empty ExtractorLoader."""
        self._registry: dict[str, type[Extractor]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, cls: type[Extractor], *, name: str | None = None) -> None:
        """Register a custom extractor class.

        Args:
            cls: The extractor class to register.  Must subclass
                :class:`Extractor` and implement all abstract methods.
            name: Override the name used for registration.  Defaults to the
                value of ``cls().name`` or ``cls.__name__`` if the class
                requires constructor arguments.

        Raises:
            :class:`ExtractorValidationError`: If *cls* fails validation.
            :class:`ValueError`: If an extractor with the same name is
                already registered.
        """
        validate_extractor(cls)

        if name is None:
            # Try to get name from a no-arg instantiation; fall back to class name
            try:
                init_sig = inspect.signature(cls.__init__)
                required = [
                    p
                    for pname, p in init_sig.parameters.items()
                    if pname != "self"
                    and p.default is inspect.Parameter.empty
                    and p.kind
                    not in (
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    )
                ]
                name = cls().name if not required else cls.__name__.lower()
            except Exception:
                name = cls.__name__.lower()

        if name in self._registry:
            msg = f"Extractor already registered: {name!r}"
            raise ValueError(msg)

        self._registry[name] = cls
        logger.debug("Registered custom extractor %r -> %s", name, cls.__name__)

    def register_or_replace(
        self, cls: type[Extractor], *, name: str | None = None
    ) -> None:
        """Register a custom extractor, replacing any existing entry with the same name.

        Used for hot-reloading: replace an extractor class at runtime without
        restarting the process.

        Args:
            cls: The extractor class to register.
            name: Optional name override.  Defaults to same logic as
                :meth:`register`.

        Raises:
            :class:`ExtractorValidationError`: If *cls* fails validation.
        """
        validate_extractor(cls)

        if name is None:
            try:
                init_sig = inspect.signature(cls.__init__)
                required = [
                    p
                    for pname, p in init_sig.parameters.items()
                    if pname != "self"
                    and p.default is inspect.Parameter.empty
                    and p.kind
                    not in (
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    )
                ]
                name = cls().name if not required else cls.__name__.lower()
            except Exception:
                name = cls.__name__.lower()

        old = self._registry.get(name)
        self._registry[name] = cls
        if old is not None:
            logger.info(
                "Hot-reloaded extractor %r: %s -> %s",
                name,
                old.__name__,
                cls.__name__,
            )
        else:
            logger.debug("Registered extractor %r -> %s", name, cls.__name__)

    def unregister(self, name: str) -> None:
        """Remove a registered extractor by name.

        Args:
            name: The registered extractor name.

        Raises:
            :class:`KeyError`: If no extractor with that name is registered.
        """
        if name not in self._registry:
            msg = f"No extractor registered with name: {name!r}"
            raise KeyError(msg)
        del self._registry[name]
        logger.debug("Unregistered extractor %r", name)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def load_from_entry_points(self) -> list[str]:
        """Discover and register extractors from installed package entry points.

        Scans all installed packages for entry points in the
        ``kutana.extractors`` group.  Each entry point should point to an
        :class:`Extractor` subclass.

        Example ``pyproject.toml`` in a custom extractor package::

            [project.entry-points."kutana.extractors"]
            compliance = "my_package.extractors:ComplianceExtractor"

        Returns:
            List of extractor names that were successfully loaded.

        Note:
            Entry points that fail to load or validate are logged as warnings
            and skipped rather than raising.
        """
        from importlib.metadata import entry_points

        loaded: list[str] = []
        eps = entry_points(group=ENTRY_POINT_GROUP)
        for ep in eps:
            try:
                cls = ep.load()
                self.register_or_replace(cls, name=ep.name)
                loaded.append(ep.name)
                logger.info(
                    "Loaded extractor %r from entry point %s", ep.name, ep.value
                )
            except Exception as exc:
                logger.warning(
                    "Failed to load extractor entry point %r (%s): %s",
                    ep.name,
                    ep.value,
                    exc,
                )
        return loaded

    def load_from_file(self, path: str | Path, *, name: str | None = None) -> list[str]:
        """Load and register extractor(s) from a local Python source file.

        Imports the file as a module and registers all :class:`Extractor`
        subclasses defined in it.

        Args:
            path: Path to the ``.py`` file containing the extractor class(es).
            name: Optional name override (only used if exactly one extractor
                is found in the file).

        Returns:
            List of extractor names that were successfully registered.

        Raises:
            :class:`FileNotFoundError`: If the file does not exist.
            :class:`ImportError`: If the file cannot be imported.
        """
        file_path = Path(path)
        if not file_path.exists():
            msg = f"Extractor file not found: {file_path}"
            raise FileNotFoundError(msg)

        module_name = f"_kutana_custom_extractor_{file_path.stem}_{id(file_path)}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            msg = f"Cannot create module spec for: {file_path}"
            raise ImportError(msg)

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        # Find all Extractor subclasses defined in this module
        candidates: list[type[Extractor]] = [
            obj
            for obj in vars(module).values()
            if isinstance(obj, type)
            and issubclass(obj, Extractor)
            and obj is not Extractor
            and obj.__module__ == module_name
        ]

        if not candidates:
            logger.warning("No Extractor subclasses found in %s", file_path)
            return []

        loaded: list[str] = []
        for _i, cls in enumerate(candidates):
            use_name = name if (name is not None and len(candidates) == 1) else None
            try:
                self.register_or_replace(cls, name=use_name)
                loaded.append(use_name or cls.__name__.lower())
            except Exception as exc:
                logger.warning(
                    "Failed to register extractor %s from %s: %s",
                    cls.__name__,
                    file_path,
                    exc,
                )
        return loaded

    def load_from_module(
        self, module_path: str, class_name: str | None = None
    ) -> list[str]:
        """Load extractor(s) from a dotted Python module path.

        Args:
            module_path: Dotted module path (e.g. ``"my_package.extractors"``).
            class_name: Optional specific class name to load.  If omitted,
                all :class:`Extractor` subclasses in the module are loaded.

        Returns:
            List of extractor names that were successfully registered.

        Raises:
            :class:`ImportError`: If the module cannot be imported.
        """
        module = importlib.import_module(module_path)
        candidates: list[type[Extractor]]
        if class_name is not None:
            cls = getattr(module, class_name, None)
            if cls is None:
                msg = f"Class {class_name!r} not found in module {module_path!r}"
                raise ImportError(msg)
            candidates = [cls]
        else:
            candidates = [
                obj
                for obj in vars(module).values()
                if isinstance(obj, type)
                and issubclass(obj, Extractor)
                and obj is not Extractor
            ]

        loaded: list[str] = []
        for cls in candidates:
            try:
                self.register_or_replace(cls)
                loaded.append(cls.__name__.lower())
            except Exception as exc:
                logger.warning(
                    "Failed to register extractor %s: %s", cls.__name__, exc
                )
        return loaded

    # ------------------------------------------------------------------
    # Instantiation
    # ------------------------------------------------------------------

    def create(self, name: str, **kwargs: Any) -> Extractor:
        """Instantiate a registered extractor by name.

        Args:
            name: The registered extractor name.
            **kwargs: Arguments forwarded to the extractor constructor.

        Returns:
            An instance of the registered extractor class.

        Raises:
            :class:`KeyError`: If no extractor with that name is registered.
        """
        cls = self._registry.get(name)
        if cls is None:
            available = sorted(self._registry)
            msg = f"No extractor registered with name {name!r}. Available: {available}"
            raise KeyError(msg)
        return cls(**kwargs)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def extractors(self) -> dict[str, type[Extractor]]:
        """Return a snapshot of the current extractor registry.

        Returns:
            Dict mapping extractor names to their class objects.
        """
        return dict(self._registry)

    def is_registered(self, name: str) -> bool:
        """Check whether an extractor name is registered.

        Args:
            name: The extractor name to check.

        Returns:
            True if registered, False otherwise.
        """
        return name in self._registry

    def __repr__(self) -> str:
        """Return a debug representation showing registered extractor names."""
        names = sorted(self._registry)
        return f"ExtractorLoader(extractors={names!r})"
