import platform
import subprocess
import sys

from security import venvpath


def test_tag_names_os_arch_and_a_hash_of_the_repo_path(tmp_path):
    system, machine = platform.system().lower(), platform.machine().lower()
    assert venvpath.tag(tmp_path).startswith(f"{system}-{machine}-")
    assert len(venvpath.tag(tmp_path).rsplit("-", 1)[1]) == 6


def test_same_platform_but_different_repo_paths_get_different_venvs(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    assert venvpath.venv_path(first) != venvpath.venv_path(second)
    assert venvpath.venv_path(first) == venvpath.venv_path(first)


def test_a_symlinked_checkout_gets_the_tag_of_its_real_path(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    assert venvpath.venv_path(link) == link / ".venvs" / venvpath.tag(real)


def test_the_launcher_asks_the_module_for_the_path():
    out = subprocess.check_output([sys.executable, venvpath.__file__], text=True).strip()
    assert out == str(venvpath.venv_path(venvpath.ROOT))
