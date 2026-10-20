# 套件設定：一般（非 editable）安裝也要包含 fixlab 底下的每個子套件，而且只包含它們。
# 不在測試裡建 wheel（要網路下載建置依賴），改成照 setuptools 的規則讀 pyproject.toml 的設定，和實際的目錄比對。

import tomllib
from fnmatch import fnmatchcase
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find_settings() -> dict:
    """pyproject.toml 裡 setuptools 自動尋找套件的設定；沒有就是空的（代表還是固定清單）。"""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packages = config.get("tool", {}).get("setuptools", {}).get("packages", {})
    return packages.get("find", {}) if isinstance(packages, dict) else {}


def included(name: str, settings: dict) -> bool:
    """和 setuptools 一樣比對套件名稱：沒寫 include 等於 ["*"]（全部包含），再扣掉 exclude。"""
    include = settings.get("include", ["*"])
    return (any(fnmatchcase(name, pattern) for pattern in include)
            and not any(fnmatchcase(name, pattern) for pattern in settings.get("exclude", [])))


def find_packages(folder: Path = ROOT, prefix: str = "") -> list[str]:
    """照 setuptools（namespaces 關閉）的方式找套件：只有含 __init__.py 的資料夾才算，
    不是套件的資料夾不再往下找；名稱含點、以點開頭的資料夾（.venv、.git）略過。"""
    found = []
    for child in sorted(folder.iterdir()):
        if not child.is_dir() or "." in child.name or not (child / "__init__.py").is_file():
            continue
        name = prefix + child.name
        found += [name, *find_packages(child, name + ".")]
    return found


def fixlab_packages() -> list[str]:
    """fixlab 底下所有含 __init__.py 的目錄（遞迴，不管上層是不是套件），轉成套件名稱。"""
    return sorted(".".join(init.parent.relative_to(ROOT).parts) for init in (ROOT / "fixlab").rglob("__init__.py"))


def test_discovery_is_configured_from_the_project_root_without_namespaces():
    # 沒有 __init__.py 的資料夾也會被 setuptools 當成套件（namespace），比對目錄的結果就不準了，所以要關掉。
    settings = find_settings()
    assert settings, "pyproject.toml has no [tool.setuptools.packages.find]"
    assert settings.get("where", ["."]) == ["."]
    assert settings.get("namespaces") is False


def test_every_fixlab_package_is_installed():
    # 用遞迴列出的目錄和 setuptools 實際找得到的比對：上層漏了 __init__.py 時，setuptools 不會往下找，子套件就沒被打包。
    settings = find_settings()
    expected = fixlab_packages()
    assert "fixlab.bench" in expected
    installed = [name for name in find_packages() if included(name, settings)]
    missing = sorted(set(expected) - set(installed))
    assert missing == [], f"not found or not included by setuptools: {missing}"


def test_only_fixlab_packages_are_installed():
    settings = find_settings()
    installed = [name for name in find_packages() if included(name, settings)]
    assert installed and all(name == "fixlab" or name.startswith("fixlab.") for name in installed), installed
    for name in ["tests", "tests.fixtures", "bench", "bench.problems", "docs"]:
        assert not included(name, settings), name
