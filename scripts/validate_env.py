#!/usr/bin/env python3
"""Validate .env file against settings.py requirements."""

import sys
from pathlib import Path


def get_env_example_vars(env_example_path: Path) -> set[str]:
    """Extract variable names from .env.example.

    Args:
        env_example_path: Path to .env.example file.

    Returns:
        Set of variable names.
    """
    variables: set[str] = set()

    if not env_example_path.exists():
        print(f"ERROR: {env_example_path} not found")
        sys.exit(1)

    with open(env_example_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                var_name = line.split("=")[0].strip()
                variables.add(var_name)

    return variables


def get_settings_vars() -> set[str]:
    """Extract required variable names from Settings class.

    Returns:
        Set of variable names (converted to uppercase).
    """
    # Import here to avoid circular imports and ensure proper path
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    from telegram_bot.config.settings import Settings

    # Get field names from Pydantic model
    variables: set[str] = set()
    for field_name, field_info in Settings.model_fields.items():
        # Convert field name to uppercase (env var convention)
        env_name = field_name.upper()
        variables.add(env_name)

    return variables


def validate() -> bool:
    """Validate .env.example against settings.py.

    Returns:
        True if validation passes, False otherwise.
    """
    project_root = Path(__file__).parent.parent
    env_example_path = project_root / ".env.example"

    env_vars = get_env_example_vars(env_example_path)
    settings_vars = get_settings_vars()

    missing_in_env = settings_vars - env_vars
    extra_in_env = env_vars - settings_vars

    is_valid = True

    if missing_in_env:
        print("ERROR: Variables in settings.py missing from .env.example:")
        for var in sorted(missing_in_env):
            print(f"  - {var}")
        is_valid = False

    if extra_in_env:
        print("WARNING: Extra variables in .env.example not in settings.py:")
        for var in sorted(extra_in_env):
            print(f"  - {var}")
        # Extra variables are just warnings, not errors

    if is_valid:
        print("SUCCESS: .env.example is valid and matches settings.py")
        print(f"  - Variables defined: {len(env_vars)}")

    return is_valid


def main() -> None:
    """Main entry point."""
    if not validate():
        sys.exit(1)


if __name__ == "__main__":
    main()
