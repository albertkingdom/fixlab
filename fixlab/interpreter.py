"""run_tests 用哪個 Python 直譯器，以及沙箱要放行它的哪些目錄。

直譯器只由使用者決定：--python 指定的，沒給就是 fixlab 自己的。不自動偵測專案裡的 .venv：
被修的專案可能是剛 clone 的陌生程式碼，偵測等於讓它的檔案決定執行什麼、沙箱放行什麼。
使用者打 --python 是明確的信任表示。路徑轉成絕對路徑但不解析符號連結：venv 的 python 是連結，解析後就找不到 venv 的套件。

基底 Python（venv 是從哪個 Python 建的）從 pyvenv.cfg 讀，再嚴格檢查才放行：沙箱擋住家目錄，
放行基底等於在家目錄上開一個洞，所以它必須真的是一個 Python 安裝，而且不能碰到任何受保護的目錄。
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MIN_VERSION = (3, 11)  # run_tests 用 python -P 啟動 pytest，-P 是 3.11 才有的
CHECK_TIMEOUT_S = 10
CHECK_MARKER = "FIXLAB-CHECK"
# 啟動前的檢查程式：先印帶前綴的版本，再匯入 pytest。不加 -P：舊版本不認得它，會連版本都印不出來；
# 也不加 -E、-s，讓模組搜尋路徑和 run_tests 一致。只解析帶前綴的那一行，.pth 在啟動時印的東西不影響。
CHECK_CODE = f"import sys; print('{CHECK_MARKER} %d.%d' % sys.version_info[:2], flush=True); import pytest"


def choose_interpreter(option: str | None) -> tuple[str, str]:
    """回傳 (直譯器路徑, 來源)。含路徑分隔符號的值以目前目錄轉成絕對路徑；裸名稱（python3）從 PATH 找，
    找不到就原樣回傳，交給檢查報錯。"""
    if option is None:
        return sys.executable, "default"
    if os.sep in option or (os.altsep and os.altsep in option):
        return str(Path(option).expanduser().absolute()), "option"
    found = shutil.which(option)  # PATH 裡可能有相對路徑的項目，找到的結果也要轉成絕對路徑
    return (str(Path(found).absolute()) if found else option), "option"


def environment_of(python: str) -> Path:
    """直譯器所屬的環境目錄：路徑往上兩層（.venv/bin/python → .venv），不解析連結。"""
    return Path(python).absolute().parent.parent


def find_base(python: str, root: Path, project_root: Path, deny_read=()) -> Path:
    """沙箱要放行的基底 Python 安裝目錄（真實路徑）。不符合下列任一條就丟出 ValueError（訊息給使用者看）：
    pyvenv.cfg 的 home 是絕對路徑、基底底下有標準函式庫、不是家目錄或上層、
    不是工作目錄、fixlab 專案目錄、deny_read 本身或在它們裡面，也不包含工作目錄或 deny_read。
    基底「包含」fixlab 專案目錄是允許的：fixlab 用 pip 裝進一般的 Python 時，它就在那個 Python 的 site-packages 裡。
    環境目錄本身也不能是家目錄或上層。"""
    environment = environment_of(python)
    is_venv = (environment / "pyvenv.cfg").is_file()
    if is_venv:
        # 只有 venv 的環境目錄會被放行讀取（見 readable_environment），所以只有它要檢查；
        # 不是 venv 的直譯器（~/bin/python3）往上兩層就算是家目錄也沒關係，那裡不會被放行。
        refuse_home_or_above(environment, "the environment of the test interpreter")
        for folder in deny_read:
            if inside_or_same(environment, folder) or inside_or_same(folder, environment):
                raise ValueError(f"the environment of the test interpreter ({environment}) overlaps "
                                 f"a folder the tests may not read ({folder}); pass a different --python")
        # 放行環境會蓋過對 fixlab 自己目錄的拒絕（例如 checkout 本身就是 venv，測試會讀到它的 .env）。
        if exposes_fixlab(environment, project_root):
            raise ValueError(f"the environment of the test interpreter ({environment}) contains fixlab's own "
                             f"directory ({project_root}); pass a different --python")
    home = read_home(environment / "pyvenv.cfg")
    if home is not None and not Path(home).is_absolute():
        # 相對路徑會依 fixlab 的目前目錄解析，結果不可預期，也能被寫成指向家目錄裡的任何地方
        raise ValueError(f"the home value {home!r} in {environment / 'pyvenv.cfg'} is not an absolute path")
    base = base_install(python, environment, home)
    refuse_home_or_above(base, "the base Python of the test interpreter")
    if not has_standard_library(base):
        raise ValueError(f"the base Python of the test interpreter is {base}, "
                         "which has no Python standard library (lib/python3.N/os.py); pass a different --python")
    if exposes_fixlab(base, project_root):
        raise ValueError(f"the base Python of the test interpreter is {base}, which contains fixlab's own "
                         f"directory ({project_root}); pass a different --python")
    checks = [("the project", root, True), ("fixlab's own directory", project_root, False),
              *(("a folder the tests may not read", folder, True) for folder in deny_read)]
    for name, folder, may_not_contain in checks:
        if inside_or_same(base, folder) or (may_not_contain and inside_or_same(folder, base)):
            raise ValueError(f"the base Python of the test interpreter is {base}, which overlaps {name} ({folder}); "
                             "pass a different --python")
    return base


def exposes_fixlab(folder: Path, project_root: Path) -> bool:
    """放行 folder 會不會連 fixlab 自己的目錄一起放行。folder 包含它時才算；例外是它在 folder 的 site-packages 裡
    （fixlab 用 uv tool、pipx 或 pip 安裝的情況），那裡只有已安裝的程式，沒有 checkout 的 .env。比對檔案系統身分。"""
    names = []
    for candidate in [Path(project_root).resolve(), *Path(project_root).resolve().parents]:
        if same_entry(candidate, folder):
            return "site-packages" not in names
        names.append(candidate.name)
    return False


def base_install(python: str, environment: Path, home: str | None) -> Path:
    """基底安裝目錄：直譯器解析連結後的真實位置往上兩層。venv 的 python 通常是指向基底的連結，
    這樣也跟得過一整個放捷徑的資料夾（~/.local/bin）。解析後還在環境裡（用 --copies 建的 venv）才退回 pyvenv.cfg 的 home。"""
    real = Path(python).resolve()
    if inside_or_same(real, environment) and home:
        return Path(home).resolve().parent
    return real.parent.parent


def readable_environment(python: str, base: Path) -> Path:
    """沙箱要放行讀取的環境目錄。只有真的 venv（有 pyvenv.cfg）才放行直譯器往上兩層的目錄；
    不是 venv 的直譯器（例如 ~/.local/bin/python3 這種捷徑）往上兩層可能是 ~/.local，不能整個放行，只放行基底。"""
    environment = environment_of(python)
    return environment if (environment / "pyvenv.cfg").is_file() else base


# 標準函式庫的位置：一般的安裝（uv、pyenv、python.org）在 lib/python3.N；
# Homebrew 的 framework 安裝在 Frameworks/Python.framework/Versions/3.N/lib/python3.N。
STDLIB_PATTERNS = ("lib/python3.*/os.py", "Frameworks/Python.framework/Versions/3.*/lib/python3.*/os.py")


def has_standard_library(base: Path) -> bool:
    return any(any(base.glob(pattern)) for pattern in STDLIB_PATTERNS)


def read_home(config: Path) -> str | None:
    """pyvenv.cfg 的 home 值；檔案不存在、沒寫或是空白就是 None。格式是每行「鍵 = 值」。"""
    try:
        lines = config.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and key.strip() == "home" and value.strip():
            return value.strip()
    return None


def inside_or_same(folder: Path, other: Path) -> bool:
    """folder 就是 other，或在 other 底下。先解析成真實路徑，再比對檔案系統身分：沙箱比對路徑不分大小寫，
    這裡也不能因為寫法不同就判斷成「不重疊」。"""
    return within(Path(folder).resolve(), other)


MAX_LINK_HOPS = 40


def link_chain(path: str) -> tuple[list[Path], Path]:
    """一個一個路徑元件解析 path，回傳 (經過的符號連結所在位置, 最後的真實路徑)。
    連結所在位置是連結檔案本身的路徑（它的上層已經解析過），不解析連結本身。"""
    pending = list(Path(path).absolute().parts)
    current = Path(pending.pop(0))
    links, hops = [], 0
    while pending:
        part = pending.pop(0)
        if part in ("", "."):
            continue
        if part == "..":
            current = current.parent
            continue
        candidate = current / part
        if candidate.is_symlink():
            hops += 1
            if hops > MAX_LINK_HOPS:
                raise ValueError(f"too many symbolic links while resolving {path}")
            links.append(candidate)
            target = Path(os.readlink(candidate))
            if target.is_absolute():
                current = Path(target.anchor)
                pending = list(target.parts[1:]) + pending
            else:
                pending = list(target.parts) + pending  # 相對於連結所在的資料夾，也就是 current
        else:
            current = candidate
    return links, current


def same_entry(path: Path, folder: Path) -> bool:
    """path（不跟隨連結）與 folder 是不是檔案系統上的同一個項目。比對裝置與 inode，不比字面：
    macOS 的檔案系統不分大小寫，同一個資料夾可以寫成 Proj 或 proj。"""
    try:
        a, b = os.lstat(path), os.stat(folder)
    except OSError:
        return False
    return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


def within(path: Path, folder: Path) -> bool:
    """path 就是 folder 或在它底下。path 本身可能是連結，不解析它；比對的是檔案系統上的身分，不受大小寫影響。"""
    path = Path(path)
    return any(same_entry(candidate, folder) for candidate in [path, *path.parents])


def refuse_unsafe_chain(python: str, root: Path) -> None:
    """從 python 一路跟符號連結到真正的執行檔，經過的每個位置都必須在專案外面；
    唯一的例外是專案裡一個真的 venv 資料夾（本身與上層都不是連結、有 pyvenv.cfg），它整個會被鎖住不能寫、不能刪、不能改名。
    專案裡其他任何位置被測的程式都寫得到：換掉其中一個連結或執行檔，下一次 run_tests 就跑假的 Python。"""
    root = Path(root).resolve()
    environment = environment_of(python).resolve()
    if within(environment, root) and not (environment / "pyvenv.cfg").is_file():
        raise ValueError(f"the environment of the test interpreter ({environment}) is inside the project but has no "
                         "pyvenv.cfg; only a virtual environment can be used from inside the project")
    links, real = link_chain(python)
    for place in links:
        if within(place, root) and not within(place, environment):
            raise ValueError(f"the test interpreter {python} goes through the symbolic link {place} inside the project, "
                             "which the tests could replace; pass the real path with --python")
    if within(real, root) and not within(real, environment):
        raise ValueError(f"the test interpreter {python} is the file {real} inside the project, outside a virtual "
                         "environment; the tests could replace it")


def refuse_home_or_above(folder: Path, what: str) -> None:
    real = Path(folder).resolve()
    if within(Path.home().resolve(), real):  # 家目錄就是它或在它底下；比對檔案系統身分，不受大小寫影響
        raise ValueError(f"{what} is {real}, which is your home directory or above; "
                         "the sandbox would have to open all of it. Pass a different --python")


def parse_version(output: str) -> tuple[int, int] | None:
    """檢查程式的輸出裡，帶前綴的那一行版本（例如 FIXLAB-CHECK 3.12）。其他行不管；找不到就是 None。"""
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == CHECK_MARKER:
            major, _, minor = parts[1].partition(".")
            if major.isdigit() and minor.isdigit():
                return int(major), int(minor)
    return None


def check_interpreter(ws) -> None:
    """啟動前檢查 Workspace 的測試用直譯器：存在、可執行、環境不包含工作目錄、3.11 以上、匯入得了 pytest。
    不符合就丟出 ValueError。執行檢查程式時包在和 run_tests 完全相同的沙箱裡（同樣的讀寫規則與測試保護），
    目前目錄設成私有暫存目錄，專案裡的 pytest.py 才不會冒充真的 pytest。"""
    # 在函式裡匯入：sandbox 與 workspace 都匯入本模組，放在檔案開頭會循環匯入。
    from fixlab.sandbox import sandbox_available, wrap_command
    from fixlab.tools import child_environment

    python = ws.python
    path = Path(python)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(f"the test interpreter {python} does not exist or is not executable; pass a different --python")
    refuse_unsafe_chain(python, ws.root)
    environment = ws.environment
    if within(ws.root, environment):
        raise ValueError(f"the environment of the test interpreter ({environment}) contains the project {ws.root}; "
                         "pass an interpreter whose environment is outside the project or inside one of its folders")
    with tempfile.TemporaryDirectory(prefix="fixlab-check-") as tmp:
        tmpdir = Path(tmp).resolve()
        command = [python, "-c", CHECK_CODE]
        if sandbox_available():
            # 只有沙箱要放行基底；沒有沙箱的平台不算它（標準函式庫的位置因平台而異）。不能放行時在這裡丟出 ValueError，
            # 算過一次後，之後的 run_tests 都用同一個值。
            command = wrap_command(command, ws.root, python, ws.project_root, ws.deny_read, tmpdir,
                                   ws.protect_tests, base=ws.base)
        try:
            done = subprocess.run(command, cwd=tmpdir, env=child_environment(tmpdir), stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, timeout=CHECK_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            raise ValueError(f"the test interpreter {python} did not start within {CHECK_TIMEOUT_S}s") from None
        except OSError as error:
            raise ValueError(f"the test interpreter {python} cannot be started: {error}") from None
    version = parse_version(done.stdout)
    if version is None:
        detail = done.stderr.strip().splitlines()[-1:] or ["no output"]
        raise ValueError(f"the test interpreter {python} failed to start: {detail[0]}")
    major, minor = version
    if (major, minor) < MIN_VERSION:
        raise ValueError(f"the test interpreter {python} is Python {major}.{minor}; "
                         "fixlab needs 3.11 or newer to run tests")
    if done.returncode != 0:
        raise ValueError(f"the test interpreter {python} cannot import pytest; "
                         "install pytest into that environment or pass a different --python")
