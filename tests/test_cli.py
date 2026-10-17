# fixlab 最小入口的測試：用假 client，不需要真的 LLM。
# 目前只涵蓋 3.6：參數與錯誤、每步輸出、快照 diff。結束後再跑 run_tests 與含 edit_file 的 diff 留給 3.11。
# 一律先把 fixture 複製到暫存目錄再當 PATH：fixlab 會直接修改指定的目錄。
import pytest

from fixlab.cli import DEFAULT_TASK, diff_report, main, take_snapshot
from test_fixture import copy_fixture  # 把 timelog 複製到暫存目錄
from test_loop import FakeClient, native  # 依序回傳劇本回覆的假 client


@pytest.fixture
def project(tmp_path):
    return copy_fixture(tmp_path)


def run_fix(project, client, *extra):
    return main([str(project), "--model", "m", *extra], client=client)


# ── main：端到端 ──────────────────────────────────────────────────────────


def test_read_only_run_leaves_directory_unchanged(project, capsys):
    before = take_snapshot(project)
    client = FakeClient([(None, [native("read_file", path="timelog/parser.py")]), ("Done.", None)])

    code = run_fix(project, client)

    out, err = capsys.readouterr()
    assert code == 0
    assert take_snapshot(project) == before
    assert "no changes" in out
    assert "stop reason: done  steps: 2" in out
    assert f"editing in place: {project}" in err


def test_each_tool_call_prints_one_line_with_name_and_ok(project, capsys):
    client = FakeClient([
        (None, [native("list_files")]),
        (None, [native("read_file", path="timelog/missing.py")]),
        ("Done.", None),
    ])

    run_fix(project, client)

    step_lines = [line for line in capsys.readouterr().err.splitlines() if "ok=" in line]
    assert step_lines == ["list_files  ok=True  flags={}", "read_file  ok=False  flags={}"]


def test_symlink_pointing_outside_is_blocked(project, tmp_path, capsys):
    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret-value\n")
    (project / "link.txt").symlink_to(secret)
    client = FakeClient([(None, [native("read_file", path="link.txt")]), ("Done.", None)])

    run_fix(project, client)

    err = capsys.readouterr().err
    assert "read_file  ok=False  flags={'blocked': True}" in err
    tool_message = client.sent[1][-1]["content"]  # 模型第二次請求看到的工具結果
    assert "top-secret-value" not in tool_message


def test_default_task_can_be_overridden(project):
    default_client = FakeClient([("Done.", None)])
    run_fix(project, default_client)
    assert default_client.sent[0][1] == {"role": "user", "content": DEFAULT_TASK}

    custom_client = FakeClient([("Done.", None)])
    run_fix(project, custom_client, "--task", "Look at report.py")
    assert custom_client.sent[0][1] == {"role": "user", "content": "Look at report.py"}


# ── main：錯誤情境 ────────────────────────────────────────────────────────


def test_missing_api_key_is_an_error(project, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    code = main([str(project), "--model", "m"])  # 沒有注入 client，會走建立真 client 的路

    assert code == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_missing_model_is_an_error(project, monkeypatch, capsys):
    monkeypatch.delenv("FIXLAB_MODEL", raising=False)
    client = FakeClient([])

    code = main([str(project)], client=client)

    assert code == 2
    assert "no model" in capsys.readouterr().err
    assert client.sent == []  # agent 沒有被啟動


def test_path_that_is_not_a_directory_is_an_error(tmp_path, capsys):
    client = FakeClient([])

    code = run_fix(tmp_path / "nope", client)

    assert code == 2
    assert "not a directory" in capsys.readouterr().err
    assert client.sent == []


# ── take_snapshot ─────────────────────────────────────────────────────────


def test_snapshot_skips_ignored_dirs_and_symlinks(tmp_path):
    (tmp_path / "a.py").write_bytes(b"x = 1\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_bytes(b"y = 2\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_bytes(b"[core]\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "a.pyc").write_bytes(b"\x00")
    (tmp_path / "link.py").symlink_to(tmp_path / "a.py")

    assert take_snapshot(tmp_path) == {"a.py": b"x = 1\n", "sub/b.py": b"y = 2\n"}


# ── diff_report ───────────────────────────────────────────────────────────


def test_diff_shows_modified_file():
    out = diff_report({"a.py": b"x = 1\n"}, {"a.py": b"x = 2\n"})
    assert "--- a/a.py" in out and "+++ b/a.py" in out
    assert "-x = 1" in out and "+x = 2" in out


def test_diff_shows_new_file():
    out = diff_report({}, {"new.py": b"hi\n"})
    assert "new file: new.py" in out and "+hi" in out


def test_diff_shows_deleted_file():
    out = diff_report({"gone.py": b"bye\n"}, {})
    assert "deleted file: gone.py" in out and "-bye" in out


def test_diff_marks_non_utf8_file_as_binary():
    out = diff_report({"blob.bin": b"\xff\xfe"}, {"blob.bin": b"\x00\xff"})
    assert out == "binary file changed: blob.bin"


def test_diff_shows_tampered_test_file():
    out = diff_report({"tests/test_report.py": b"assert 1 == 2\n"}, {"tests/test_report.py": b"assert True\n"})
    assert "tests/test_report.py" in out and "+assert True" in out


def test_diff_skips_unchanged_files():
    out = diff_report({"a.py": b"x = 1\n", "b.py": b"y\n"}, {"a.py": b"x = 2\n", "b.py": b"y\n"})
    assert "b.py" not in out


def test_diff_says_no_changes_when_nothing_changed():
    assert diff_report({"a.py": b"x\n"}, {"a.py": b"x\n"}) == "no changes"


def test_diff_explains_final_newline_only_change():
    out = diff_report({"a.py": b"x\n"}, {"a.py": b"x"})
    assert out == "a.py: only line endings or the final newline changed"
