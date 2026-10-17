# 事件檔的單元測試：對應 run-telemetry 規格的 One event file per run、Four event types、
# Each line is written immediately、Logging failures never stop the run。
import json
import re
from datetime import datetime, timezone

import pytest

from fixlab.telemetry import EventLog, default_log_dir

START = datetime(2026, 10, 18, 9, 30, 5, 123000, tzinfo=timezone.utc)


def at_start():
    return START


def read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# Scenario: Default location and name
def test_default_location_and_name(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    log = EventLog(default_log_dir(), "qwen/qwen3.5-9b", now=at_start)
    assert log.path == tmp_path / ".fixlab" / "runs" / "20261018T093005Z-qwen-qwen3.5-9b" / "events.jsonl"
    assert log.path.exists()


# Scenario: Custom log directory
def test_custom_log_directory(tmp_path):
    log = EventLog(tmp_path / "exp1", "m", now=at_start)
    assert log.path == tmp_path / "exp1" / "20261018T093005Z-m" / "events.jsonl"


def test_characters_outside_the_allowed_set_become_a_dash_in_the_model_name(tmp_path):
    log = EventLog(tmp_path, "vendor/model:7b q4", now=at_start)
    assert log.path.parent.name == "20261018T093005Z-vendor-model-7b-q4"


# Scenario: Name already taken
def test_a_taken_name_gets_a_numeric_suffix_and_the_old_file_is_untouched(tmp_path):
    first = EventLog(tmp_path, "m", now=at_start)
    first.write("run_start", n=1)
    second = EventLog(tmp_path, "m", now=at_start)
    third = EventLog(tmp_path, "m", now=at_start)
    second.write("run_start", n=2)

    assert second.path.parent.name == "20261018T093005Z-m-2"
    assert third.path.parent.name == "20261018T093005Z-m-3"
    assert [line["n"] for line in read_lines(first.path)] == [1]  # 第一個檔案沒被碰到


# Requirement: Four event types（每一行的共同欄位）
def test_every_line_has_event_and_a_utc_timestamp(tmp_path):
    log = EventLog(tmp_path, "m", now=at_start)
    log.write("run_start", schema=1, mode="once")

    (line,) = read_lines(log.path)
    assert line == {"event": "run_start", "ts": "2026-10-18T09:30:05.123Z", "schema": 1, "mode": "once"}
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", line["ts"])


def test_non_json_values_are_written_as_text_instead_of_crashing(tmp_path):
    log = EventLog(tmp_path, "m", now=at_start)
    log.write("run_start", path=tmp_path)  # Path 不是 JSON 型別
    assert read_lines(log.path)[0]["path"] == str(tmp_path)


def test_chinese_text_is_written_as_is(tmp_path):
    log = EventLog(tmp_path, "m", now=at_start)
    log.write("task_start", text="修好測試")
    assert "修好測試" in log.path.read_text(encoding="utf-8")


# Scenario: Reading while the run is still going
def test_lines_can_be_read_before_the_log_is_closed(tmp_path):
    log = EventLog(tmp_path, "m", now=at_start)
    log.write("run_start", n=1)
    log.write("task_start", n=2)

    # 沒有 close：每一行已經寫進檔案，程式被殺掉也一樣
    assert [line["event"] for line in read_lines(log.path)] == ["run_start", "task_start"]


# Scenario: Unwritable log directory
def test_an_unusable_log_directory_only_warns_once(tmp_path, capsys):
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("x")
    log = EventLog(not_a_directory, "m", now=at_start)

    log.write("run_start")
    log.write("task_start")

    err = capsys.readouterr().err
    assert err.count("warning") == 1 and "event log" in err
    assert log.path is None


def test_a_write_error_in_the_middle_stops_logging_with_one_warning(tmp_path, capsys):
    class FullDisk:
        def write(self, text):
            raise OSError("No space left on device")

        def flush(self):
            pass

    log = EventLog(tmp_path, "m", now=at_start)
    log.write("run_start", n=1)
    log._file = FullDisk()
    log.write("task_start", n=2)
    log.write("trace", n=3)

    err = capsys.readouterr().err
    assert err.count("warning") == 1 and "No space left" in err
    assert [line["n"] for line in read_lines(log.path)] == [1]  # 壞掉之前寫的還在


def test_close_is_safe_to_call_twice(tmp_path):
    log = EventLog(tmp_path, "m", now=at_start)
    log.close()
    log.close()
    with pytest.raises(ValueError):  # 關檔之後 _file 不能再用；呼叫端要在最後才 close
        log._file.write("x")
