#!/usr/bin/env bash
# Scaffold a new Convene AI feature following the ABC provider pattern
set -euo pipefail

FEATURE=${1:-}
if [[ -z "$FEATURE" ]]; then
  echo "Usage: scaffold-feature.sh <feature-name>"
  echo "  e.g. scaffold-feature.sh summarizer"
  exit 1
fi

REPO=$(git rev-parse --show-toplevel)
CORE="$REPO/packages/convene-core/src/convene_core"
PROVIDERS="$REPO/packages/convene-providers/src/convene_providers"

echo "==> Scaffolding feature: $FEATURE"

# Interface (ABC)
cat > "$CORE/interfaces/${FEATURE}.py" <<PYEOF
"""Abstract interface for ${FEATURE} provider."""
from abc import ABC, abstractmethod


class ${FEATURE^}Provider(ABC):
    """Base class for ${FEATURE} implementations."""

    @abstractmethod
    async def process(self, input: str) -> str:
        """Process input and return result.

        Args:
            input: The input to process.

        Returns:
            The processed result.
        """
        ...
PYEOF
echo "  Created: packages/convene-core/src/convene_core/interfaces/${FEATURE}.py"

# Stub provider implementation
mkdir -p "$PROVIDERS"
cat > "$PROVIDERS/${FEATURE}_provider.py" <<PYEOF
"""${FEATURE^} provider implementation."""
from convene_core.interfaces.${FEATURE} import ${FEATURE^}Provider


class Default${FEATURE^}Provider(${FEATURE^}Provider):
    """Default implementation of ${FEATURE^}Provider."""

    async def process(self, input: str) -> str:
        """Process input.

        Args:
            input: The input to process.

        Returns:
            Processed result.
        """
        raise NotImplementedError("Implement this provider")
PYEOF
echo "  Created: packages/convene-providers/src/convene_providers/${FEATURE}_provider.py"

# Test file
mkdir -p "$CORE/../../../tests"
cat > "$CORE/../../../tests/test_${FEATURE}.py" <<PYEOF
"""Tests for ${FEATURE} interface and providers."""
import pytest
from convene_providers.${FEATURE}_provider import Default${FEATURE^}Provider


@pytest.mark.asyncio
async def test_${FEATURE}_provider_stub() -> None:
    provider = Default${FEATURE^}Provider()
    with pytest.raises(NotImplementedError):
        await provider.process("test input")
PYEOF
echo "  Created: packages/convene-core/tests/test_${FEATURE}.py"

echo ""
echo "==> Next steps:"
echo "  1. Implement Default${FEATURE^}Provider in convene-providers"
echo "  2. Register in provider registry"
echo "  3. Wire into the relevant service"
echo "  4. See claude_docs/Convene_Core_Patterns.md and claude_docs/Provider_Patterns.md"
