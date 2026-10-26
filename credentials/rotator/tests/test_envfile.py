import os

import pytest

from rotator.destinations import DestinationError, EnvFile


def test_replaces_existing_assignment_and_keeps_other_lines(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# header\nA=1\nTOKEN=old\nB=2\n")
    EnvFile(path, "TOKEN").write("new-token_1")
    assert path.read_text() == "# header\nA=1\nTOKEN=new-token_1\nB=2\n"


def test_keeps_export_prefix(tmp_path):
    path = tmp_path / ".envrc"
    path.write_text("export TOKEN=old\n")
    EnvFile(path, "TOKEN").write("new")
    assert path.read_text() == "export TOKEN=new\n"


def test_appends_with_export_only_for_envrc(tmp_path):
    envrc, env = tmp_path / ".envrc", tmp_path / ".env"
    envrc.write_text("A=1")
    env.write_text("A=1\n")
    EnvFile(envrc, "TOKEN").write("t")
    EnvFile(env, "TOKEN").write("t")
    assert envrc.read_text() == "A=1\nexport TOKEN=t\n"
    assert env.read_text() == "A=1\nTOKEN=t\n"


def test_does_not_touch_variables_sharing_a_prefix(tmp_path):
    path = tmp_path / ".env"
    path.write_text("TOKEN_2=keep\nTOKEN=old\n")
    EnvFile(path, "TOKEN").write("new")
    assert path.read_text() == "TOKEN_2=keep\nTOKEN=new\n"


def test_creates_missing_file_private(tmp_path):
    path = tmp_path / ".env"
    EnvFile(path, "TOKEN").write("t")
    assert path.read_text() == "TOKEN=t\n"
    assert path.stat().st_mode & 0o777 == 0o600


def test_preserves_mode(tmp_path):
    path = tmp_path / ".env"
    path.write_text("TOKEN=old\n")
    path.chmod(0o640)
    EnvFile(path, "TOKEN").write("new")
    assert path.stat().st_mode & 0o777 == 0o640


def test_quotes_values_with_shell_metacharacters(tmp_path):
    path = tmp_path / ".env"
    EnvFile(path, "TOKEN").write("a b$c")
    assert path.read_text() == "TOKEN='a b$c'\n"


@pytest.mark.parametrize("secret", ["", "it's", "two\nlines"])
def test_rejects_values_it_cannot_quote_without_echoing_them(tmp_path, secret):
    path = tmp_path / ".env"
    path.write_text("TOKEN=old\n")
    with pytest.raises(DestinationError) as e:
        EnvFile(path, "TOKEN").write(secret)
    assert secret == "" or secret not in str(e.value)
    assert path.read_text() == "TOKEN=old\n"


def test_writes_through_symlink(tmp_path):
    real = tmp_path / "real.env"
    real.write_text("TOKEN=old\n")
    link = tmp_path / ".env"
    link.symlink_to(real)
    EnvFile(link, "TOKEN").write("new")
    assert link.is_symlink()
    assert real.read_text() == "TOKEN=new\n"


def test_restore_puts_back_previous_content(tmp_path):
    path = tmp_path / ".env"
    path.write_text("A=1\nTOKEN=old\n")
    adapter = EnvFile(path, "TOKEN")
    backup = adapter.read_current()
    adapter.write("new")
    adapter.restore(backup)
    assert path.read_text() == "A=1\nTOKEN=old\n"


def test_restore_removes_a_file_that_did_not_exist(tmp_path):
    path = tmp_path / ".env"
    adapter = EnvFile(path, "TOKEN")
    backup = adapter.read_current()
    adapter.write("new")
    adapter.restore(backup)
    assert not path.exists()


def test_backup_repr_hides_content(tmp_path):
    path = tmp_path / ".env"
    path.write_text("TOKEN=supersecret\n")
    assert "supersecret" not in repr(EnvFile(path, "TOKEN").read_current())


def test_missing_directory_is_a_clean_error(tmp_path):
    with pytest.raises(DestinationError):
        EnvFile(tmp_path / "nope" / ".env", "TOKEN").write("t")
    assert os.listdir(tmp_path) == []

