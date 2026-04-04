# Zero Tolerance for Errors and Warnings

Every lint, build, type-check, and test run must produce **zero errors and zero warnings**. No exceptions.

## When you encounter errors or warnings

1. **Fix them inline** if they're quick (unused imports, formatting, deprecation warnings, simple lint fixes).
2. **Add them to the current plan as a tracked task** if they're non-trivial or risky to fix immediately.
3. **Tell the user** if they require a decision or could have unintended side effects.

## What NOT to do

- Never dismiss errors/warnings as "pre-existing" or "not from my changes."
- Never say "all clean" or "passes" when there are warnings in the output.
- Never skip fixing something because it was broken before you touched it.

Every pass through the code is an opportunity to leave it cleaner. Ignoring known issues normalizes technical debt.
