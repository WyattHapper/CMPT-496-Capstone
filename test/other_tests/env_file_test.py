"""!
@file env_file_test.py
@brief Tests for backend/env_file.py (T-074).
@details Saving the API key used to open .env in overwrite mode and keep
only GOOGLE_API_KEY. Every case runs on a temp file, never the real .env.
"""

from backend.env_file import save_env_value


def test_other_lines_survive_a_save(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# tracing\nLANGSMITH_API_KEY=ls-123\nGOOGLE_API_KEY=old\nOTHER=1\n",
        encoding="utf-8",
    )

    save_env_value(env, "GOOGLE_API_KEY", "new")

    assert env.read_text(encoding="utf-8") == (
        "# tracing\nLANGSMITH_API_KEY=ls-123\nGOOGLE_API_KEY=new\nOTHER=1\n"
    )


def test_old_key_is_replaced_not_duplicated(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GOOGLE_API_KEY=old\n", encoding="utf-8")

    save_env_value(env, "GOOGLE_API_KEY", "new")
    save_env_value(env, "GOOGLE_API_KEY", "newer")

    assert env.read_text(encoding="utf-8") == "GOOGLE_API_KEY=newer\n"


def test_key_is_added_when_missing(tmp_path):
    # Last line has no trailing newline, as hand-edited files often don't.
    env = tmp_path / ".env"
    env.write_text("OTHER=1", encoding="utf-8")

    save_env_value(env, "GOOGLE_API_KEY", "abc")

    assert env.read_text(encoding="utf-8") == "OTHER=1\nGOOGLE_API_KEY=abc\n"


def test_file_is_created_on_first_save(tmp_path):
    env = tmp_path / ".env"

    save_env_value(env, "GOOGLE_API_KEY", "abc")

    # Unquoted, the same format main.js and load_dotenv already read.
    assert env.read_text(encoding="utf-8") == "GOOGLE_API_KEY=abc\n"
