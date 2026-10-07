"""
backend/env_file.py

Writes single values into the .env file.

Kept apart from commands.py so tests can import it without
loading ChromaDB and the agents.
"""

from dotenv import set_key


def save_env_value(env_path, key: str, value: str):
    """
    Set one key in .env, keeping every other line.

    Replaces the key's line if it exists, appends it if not, and
    creates the file if it is missing. Written unquoted
    (KEY=value) to match the format the app has always saved.
    """

    set_key(
        env_path,
        key,
        value,
        quote_mode="never"
    )
