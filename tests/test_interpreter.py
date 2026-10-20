# 測試用直譯器的選擇與基底 Python 的推算（fixlab/interpreter.py）。只建檔案與符號連結，不執行任何直譯器。

import os
import sys
from pathlib import Path

import pytest

from fixlab.interpreter import choose_interpreter, find_base, parse_version


@pytest.fixture
def home(tmp_path, monkeypatch):
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    return folder


def make_install(folder: Path, version: str = "3.12") -> Path:
    """一個看起來像 Python 安裝的資料夾：bin/python3.N 與 lib/python3.N/os.py。回傳 bin 目錄。"""
    (folder / "bin").mkdir(parents=True)
    (folder / "bin" / f"python{version}").write_text("")
    (folder / "lib" / f"python{version}").mkdir(parents=True)
    (folder / "lib" / f"python{version}" / "os.py").write_text("")
    return folder / "bin"


def make_venv(folder: Path, home_line: str | None) -> Path:
    """建一個看起來像 venv 的資料夾：bin/python 與 pyvenv.cfg（home_line 是 None 就不寫 home）。"""
    (folder / "bin").mkdir(parents=True)
    python = folder / "bin" / "python"
    python.write_text("")
    lines = ["include-system-site-packages = false", "version = 3.12.3"]
    if home_line is not None:
        lines.insert(0, f"home = {home_line}")
    (folder / "pyvenv.cfg").write_text("\n".join(lines) + "\n")
    return python


@pytest.fixture
def places(tmp_path, home):
    """find_base 需要的其他目錄：工作目錄與 fixlab 專案目錄（都是空資料夾）。"""
    root = tmp_path / "ws"
    root.mkdir()
    project = tmp_path / "fixlab-project"
    project.mkdir()
    return {"root": root, "project_root": project, "deny_read": ()}


# ── The command line chooses the test interpreter ─────────────────────────


def test_option_is_used_as_an_absolute_path(tmp_path):
    assert choose_interpreter("/some/env/bin/python") == ("/some/env/bin/python", "option")


def test_relative_option_is_made_absolute_against_the_start_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert choose_interpreter("env/bin/python") == (str(tmp_path / "env" / "bin" / "python"), "option")


def test_relative_option_keeps_symbolic_links(tmp_path, monkeypatch):
    # 不解析符號連結：venv 的 python 是連結，解析後就找不到 venv 的套件。
    (tmp_path / "env" / "bin").mkdir(parents=True)
    (tmp_path / "env" / "bin" / "python").symlink_to(sys.executable)
    monkeypatch.chdir(tmp_path)
    assert choose_interpreter("env/bin/python")[0] == str(tmp_path / "env" / "bin" / "python")


def test_bare_name_is_looked_up_on_path(tmp_path, monkeypatch):
    (tmp_path / "bin").mkdir()
    found = tmp_path / "bin" / "mypython"
    found.write_text("#!/bin/sh\n")
    found.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path / "bin") + os.pathsep + os.environ.get("PATH", ""))
    assert choose_interpreter("mypython") == (str(found), "option")


def test_bare_name_that_is_not_on_path_is_kept_for_the_check_to_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert choose_interpreter("no-such-python-xyz") == ("no-such-python-xyz", "option")


def test_without_option_fixlab_s_own_interpreter_is_used():
    assert choose_interpreter(None) == (sys.executable, "default")


# ── The sandbox allows the test interpreter and its base Python ───────────


def test_base_comes_from_pyvenv_cfg(tmp_path, places):
    base_bin = make_install(tmp_path / "pythons" / "cpython-3.12")
    python = make_venv(tmp_path / "env", str(base_bin))
    assert find_base(str(python), **places) == base_bin.parent.resolve()


def test_base_home_through_a_symbolic_link(tmp_path, places):
    # Homebrew 的 pyvenv.cfg 寫的是 opt/python@3.14/bin，它是指到 Cellar 的連結：取真實路徑的上一層。
    real = tmp_path / "Cellar" / "python" / "3.14"
    make_install(real, "3.14")
    (tmp_path / "opt").mkdir()
    (tmp_path / "opt" / "python").symlink_to(real)
    python = make_venv(tmp_path / "env", str(tmp_path / "opt" / "python" / "bin"))
    assert find_base(str(python), **places) == real.resolve()


def test_a_framework_installation_is_a_python_installation(tmp_path, places):
    # Homebrew 的標準函式庫在 Frameworks/Python.framework/Versions/3.N/lib/python3.N。
    base = tmp_path / "Cellar" / "python" / "3.14"
    (base / "bin").mkdir(parents=True)
    stdlib = base / "Frameworks" / "Python.framework" / "Versions" / "3.14" / "lib" / "python3.14"
    stdlib.mkdir(parents=True)
    (stdlib / "os.py").write_text("")
    python = make_venv(tmp_path / "env", str(base / "bin"))
    assert find_base(str(python), **places) == base.resolve()


@pytest.mark.parametrize("home_line", [None, "", "   "])
def test_without_a_home_value_the_interpreter_itself_is_used(tmp_path, places, home_line):
    # 沒有 pyvenv.cfg 或沒寫 home：取直譯器真實路徑往上兩層。
    base_bin = make_install(tmp_path / "plain")
    env = tmp_path / "env"
    python = make_venv(env, home_line)
    python.unlink()
    python.symlink_to(base_bin / "python3.12")
    if home_line is None:
        (env / "pyvenv.cfg").unlink()
    assert find_base(str(python), **places) == base_bin.parent.resolve()


# Scenario: A pyvenv.cfg that points at another folder
def test_relative_home_is_refused(tmp_path, places):
    python = make_venv(tmp_path / "env", "../../.ssh/bin")
    with pytest.raises(ValueError, match="absolute"):
        find_base(str(python), **places)


def test_home_that_is_not_a_python_installation_is_refused(tmp_path, home, places):
    (home / ".ssh" / "bin").mkdir(parents=True)
    (home / ".ssh" / "id_rsa").write_text("secret\n")
    python = make_venv(tmp_path / "env", str(home / ".ssh" / "bin"))
    with pytest.raises(ValueError, match="standard library"):
        find_base(str(python), **places)


@pytest.mark.parametrize("where", ["home", "above"])
def test_base_that_is_home_or_above_is_refused(tmp_path, home, places, where):
    target = home if where == "home" else home.parent
    make_install(target) if not (target / "bin").exists() else None
    python = make_venv(tmp_path / "env", str(target / "bin"))
    with pytest.raises(ValueError, match="home directory"):
        find_base(str(python), **places)


@pytest.mark.parametrize("protected", ["root", "project_root"])
def test_base_inside_a_protected_folder_is_refused(tmp_path, places, protected):
    base_bin = make_install(places[protected] / "py")
    python = make_venv(tmp_path / "env", str(base_bin))
    with pytest.raises(ValueError, match="overlaps"):
        find_base(str(python), **places)


def test_base_inside_a_deny_read_folder_is_refused(tmp_path, places):
    secrets = tmp_path / "secrets"
    base_bin = make_install(secrets / "py")
    python = make_venv(tmp_path / "env", str(base_bin))
    with pytest.raises(ValueError, match="overlaps"):
        find_base(str(python), **{**places, "deny_read": (secrets,)})


def test_base_that_contains_the_workspace_is_refused(tmp_path, places):
    # 基底包含工作目錄：放行基底等於連同上層一起放行。這裡讓工作目錄落在一個 Python 安裝底下。
    install = tmp_path / "install"
    base_bin = make_install(install)
    root = install / "ws"
    root.mkdir()
    python = make_venv(tmp_path / "env", str(base_bin))
    with pytest.raises(ValueError, match="overlaps"):
        find_base(str(python), **{**places, "root": root})


def test_environment_that_is_home_is_refused(tmp_path, home, places):
    # 環境目錄（直譯器往上兩層）就是家目錄：放行它等於放行整個家目錄。
    base_bin = make_install(tmp_path / "base")
    (home / "bin").mkdir()
    (home / "bin" / "python").write_text("")
    (home / "pyvenv.cfg").write_text(f"home = {base_bin}\n")
    with pytest.raises(ValueError, match="home directory"):
        find_base(str(home / "bin" / "python"), **places)


# Scenario: Startup output before the version（只解析帶前綴的那一行）
@pytest.mark.parametrize("output, expected", [
    ("FIXLAB-CHECK 3.12\n", (3, 12)),
    ("hello from a .pth\nFIXLAB-CHECK 3.11\n", (3, 11)),
    ("3.12\n", None),
    ("FIXLAB-CHECK three\n", None),
    ("", None),
])
def test_only_the_marked_version_line_counts(output, expected):
    assert parse_version(output) == expected


# ── 第二輪 review 的修正 ───────────────────────────────────────────────────


def test_bare_name_found_through_a_relative_path_entry_is_made_absolute(tmp_path, monkeypatch):
    (tmp_path / "bin").mkdir()
    found = tmp_path / "bin" / "mypython"
    found.write_text("#!/bin/sh\n")
    found.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "bin")
    assert choose_interpreter("mypython") == (str(found), "option")


def test_base_follows_the_interpreter_through_a_folder_of_shims(tmp_path, places):
    # ~/.local/bin/python3.12 -m venv：pyvenv.cfg 的 home 是一個放捷徑的資料夾，真正的安裝在捷徑指向的地方。
    install = tmp_path / "share" / "cpython-3.12"
    base_bin = make_install(install)
    shims = tmp_path / "local" / "bin"
    shims.mkdir(parents=True)
    (shims / "python3.12").symlink_to(base_bin / "python3.12")
    python = make_venv(tmp_path / "env", str(shims))
    python.unlink()
    python.symlink_to(shims / "python3.12")
    assert find_base(str(python), **places) == install.resolve()


def test_base_that_contains_fixlab_s_own_install_is_allowed(tmp_path, places):
    # fixlab 用 pip 裝進一般的 Python：fixlab 的位置是那個 Python 的 site-packages，在基底裡面。
    install = tmp_path / "python312"
    base_bin = make_install(install)
    site = install / "lib" / "python3.12" / "site-packages"
    site.mkdir()
    assert find_base(str(base_bin / "python3.12"), **{**places, "project_root": site}) == install.resolve()


def test_base_that_contains_a_deny_read_folder_is_refused(tmp_path, places):
    install = tmp_path / "python312"
    base_bin = make_install(install)
    secrets = install / "secrets"
    secrets.mkdir()
    with pytest.raises(ValueError, match="overlaps"):
        find_base(str(base_bin / "python3.12"), **{**places, "deny_read": (secrets,)})


# ── 第三輪 review：只有「不是連結、有 pyvenv.cfg」的 venv 可以放在專案裡 ──────────


def homebrew_like_python(tmp_path):
    """專案外的一個真 Python 安裝（假的檔案），回傳它的執行檔。"""
    return make_install(tmp_path / "outside" / "python3.12") / "python3.12"


def test_a_venv_inside_the_project_whose_python_points_outside_is_allowed(tmp_path, places):
    from fixlab.interpreter import refuse_unsafe_chain
    real = homebrew_like_python(tmp_path)
    env = places["root"] / ".venv"
    python = make_venv(env, str(real.parent))
    python.unlink()
    python.symlink_to(real)
    refuse_unsafe_chain(str(python), places["root"])  # 不丟例外


def test_a_hop_through_the_project_outside_the_venv_is_refused(tmp_path, places):
    # .venv/bin/python → ../../scripts/py → 真的 Python：scripts/py 在專案裡、又不在 venv 裡，被換掉就能偽造通過。
    from fixlab.interpreter import refuse_unsafe_chain
    real = homebrew_like_python(tmp_path)
    root = places["root"]
    (root / "scripts").mkdir()
    (root / "scripts" / "py").symlink_to(real)
    python = make_venv(root / ".venv", str(real.parent))
    python.unlink()
    python.symlink_to(Path("../../scripts/py"))
    with pytest.raises(ValueError, match="scripts/py"):
        refuse_unsafe_chain(str(python), root)


def test_an_environment_in_the_project_without_pyvenv_cfg_is_refused(tmp_path, places):
    from fixlab.interpreter import refuse_unsafe_chain
    real = homebrew_like_python(tmp_path)
    root = places["root"]
    (root / "tools" / "bin").mkdir(parents=True)
    (root / "tools" / "bin" / "python").symlink_to(real)
    with pytest.raises(ValueError, match="pyvenv.cfg"):
        refuse_unsafe_chain(str(root / "tools" / "bin" / "python"), root)


def test_a_linked_venv_folder_in_the_project_is_refused(tmp_path, places):
    from fixlab.interpreter import refuse_unsafe_chain
    real = homebrew_like_python(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    python = make_venv(elsewhere, str(real.parent))
    root = places["root"]
    (root / ".venv").symlink_to(elsewhere)
    with pytest.raises(ValueError, match="symbolic link"):
        refuse_unsafe_chain(str(root / ".venv" / "bin" / "python"), root)


def test_an_interpreter_outside_the_project_is_allowed_whatever_its_links(tmp_path, places):
    from fixlab.interpreter import refuse_unsafe_chain
    real = homebrew_like_python(tmp_path)
    (tmp_path / "shims").mkdir()
    (tmp_path / "shims" / "python3").symlink_to(real)
    refuse_unsafe_chain(str(tmp_path / "shims" / "python3"), places["root"])


def test_a_plain_interpreter_in_the_home_directory_is_allowed(tmp_path, home, places):
    # ~/bin/python3 指向專案外的 Python：環境（往上兩層）是家目錄，但它不是 venv，不會被放行，只放行基底。
    real = homebrew_like_python(tmp_path)
    (home / "bin").mkdir()
    (home / "bin" / "python3").symlink_to(real)
    assert find_base(str(home / "bin" / "python3"), **places) == real.parent.parent.resolve()


def test_a_venv_that_contains_a_deny_read_folder_is_refused(tmp_path, places):
    real = homebrew_like_python(tmp_path)
    env = tmp_path / "env"
    python = make_venv(env, str(real.parent))
    python.unlink()
    python.symlink_to(real)
    secrets = env / "secrets"
    secrets.mkdir()
    with pytest.raises(ValueError, match="overlaps"):
        find_base(str(python), **{**places, "deny_read": (secrets,)})


# ── 第四輪 review（與 Codex 討論後只修必要的）───────────────────────────────


def test_a_venv_that_is_fixlab_s_own_checkout_is_refused(tmp_path, places):
    # fixlab 的 checkout 本身是 venv：放行它會讓測試讀到 fixlab 的 .env。
    real = homebrew_like_python(tmp_path)
    checkout = places["project_root"]
    python = make_venv(checkout, str(real.parent))
    python.unlink()
    python.symlink_to(real)
    with pytest.raises(ValueError, match="fixlab's own directory"):
        find_base(str(python), **places)


def test_a_venv_with_fixlab_installed_in_its_site_packages_is_allowed(tmp_path, places):
    # uv tool / pipx 安裝：fixlab 在工具環境的 site-packages 裡，環境包含 fixlab 的目錄是正常的。
    real = homebrew_like_python(tmp_path)
    env = tmp_path / "tools" / "fixlab"
    python = make_venv(env, str(real.parent))
    python.unlink()
    python.symlink_to(real)
    site = env / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    assert find_base(str(python), **{**places, "project_root": site}) == real.parent.parent.resolve()


def test_a_venv_that_contains_fixlab_s_checkout_elsewhere_is_refused(tmp_path, places):
    real = homebrew_like_python(tmp_path)
    env = tmp_path / "venv"
    python = make_venv(env, str(real.parent))
    python.unlink()
    python.symlink_to(real)
    checkout = env / "src" / "fixlab"
    checkout.mkdir(parents=True)
    with pytest.raises(ValueError, match="fixlab's own directory"):
        find_base(str(python), **{**places, "project_root": checkout})


# ── 第五輪 review（與 Codex 討論後只修必要的）───────────────────────────────

case_insensitive = pytest.mark.skipif(not Path("/USERS").exists(), reason="needs a case-insensitive file system")


@case_insensitive
def test_overlap_checks_do_not_depend_on_letter_case(tmp_path, places):
    # 沙箱比對路徑不分大小寫：--python 寫成小寫，檢查也要認得那是同一個資料夾。
    real = homebrew_like_python(tmp_path)
    env = tmp_path / "Venv"
    python = make_venv(env, str(real.parent))
    python.unlink()
    python.symlink_to(real)
    checkout = env / "checkout"
    checkout.mkdir()
    lower = str(tmp_path / "venv" / "bin" / "python")
    with pytest.raises(ValueError, match="fixlab's own directory"):
        find_base(lower, **{**places, "project_root": checkout})
    with pytest.raises(ValueError, match="overlaps"):
        find_base(lower, **{**places, "deny_read": (checkout,)})


@case_insensitive
def test_home_check_does_not_depend_on_letter_case(tmp_path, home, places):
    make_install(home)
    python = make_venv(tmp_path / "env", str(Path(str(home).upper()) / "bin"))
    with pytest.raises(ValueError, match="home directory"):
        find_base(str(python), **places)


def test_a_base_that_contains_fixlab_s_checkout_is_refused(tmp_path, places):
    # 基底包含 fixlab 的 checkout（不在 site-packages 裡）：放行基底會讓測試讀到 checkout 的 .env。
    install = tmp_path / "py"
    base_bin = make_install(install)
    checkout = install / "src" / "fixlab"
    checkout.mkdir(parents=True)
    with pytest.raises(ValueError, match="fixlab's own directory"):
        find_base(str(base_bin / "python3.12"), **{**places, "project_root": checkout})
