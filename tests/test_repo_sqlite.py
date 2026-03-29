"""
Tests for SqliteRepo (the actual active repo implementation).

These tests run without PySide6 and without pytest — execute via:
    python tests/test_repo_sqlite.py
or install pytest and run:
    pytest tests/test_repo_sqlite.py
"""
from __future__ import annotations

import sys
import tempfile
import os
import time as _time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from semetra.repo.sqlite_repo import SqliteRepo


def _make_repo() -> tuple[SqliteRepo, str]:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return SqliteRepo(db_path=f.name), f.name


# ── helpers ───────────────────────────────────────────────────────────────
PASS = FAIL = 0


def chk(cond: bool) -> None:
    if not cond:
        raise AssertionError("condition is False")


def T(label: str, fn) -> None:
    global PASS, FAIL
    try:
        fn()
        print(f"  [PASS] {label}")
        PASS += 1
    except Exception as e:
        print(f"  [FAIL] {label}  →  {e}")
        FAIL += 1


# ── tests ─────────────────────────────────────────────────────────────────

def test_settings(repo: SqliteRepo) -> None:
    print("\n=== Settings ===")
    T("get_setting unknown → None",       lambda: chk(repo.get_setting("_nope_") is None))
    T("set/get roundtrip",                lambda: [repo.set_setting("x", "y"), chk(repo.get_setting("x") == "y")])
    T("set_setting overwrites",           lambda: [repo.set_setting("x", "z"), chk(repo.get_setting("x") == "z")])
    T("hours_per_ects default=25",        lambda: chk(repo.hours_per_ects() == 25))
    repo.set_setting("hours_per_ects", "30")
    T("hours_per_ects after change=30",   lambda: chk(repo.hours_per_ects() == 30))
    repo.set_setting("hours_per_ects", "25")


def test_modules(repo: SqliteRepo) -> tuple[int, int]:
    print("\n=== Modules ===")
    mid = repo.add_module({"name": "Mathematik", "semester": "1", "ects": 4, "status": "active"})
    T("add_module returns int",           lambda: chk(isinstance(mid, int) and mid > 0))
    T("get_module by id",                 lambda: chk(repo.get_module(mid)["name"] == "Mathematik"))
    T("list_modules not empty",           lambda: chk(len(repo.list_modules()) >= 1))
    T("list_modules filter active",       lambda: chk(len(repo.list_modules("active")) >= 1))
    repo.update_module(mid, ects=6.0)
    T("update_module ects=6",             lambda: chk(float(repo.get_module(mid)["ects"]) == 6.0))
    T("get_module None for bad id",       lambda: chk(repo.get_module(9999) is None))
    mid2 = repo.add_module({"name": "Programmieren", "semester": "2", "ects": 3, "status": "planned"})
    return mid, mid2


def test_tasks(repo: SqliteRepo, mid: int) -> int:
    print("\n=== Tasks ===")
    tid = repo.add_task(mid, "Aufgabe 1", priority="High", due_date="2026-05-01")
    T("add_task returns id",              lambda: chk(isinstance(tid, int) and tid > 0))
    T("get_task",                         lambda: chk(repo.get_task(tid)["title"] == "Aufgabe 1"))
    T("list_tasks all",                   lambda: chk(len(repo.list_tasks()) >= 1))
    T("list_tasks by module",             lambda: chk(len(repo.list_tasks(module_id=mid)) >= 1))
    T("list_tasks status=Open",           lambda: chk(len(repo.list_tasks(status="Open")) >= 1))
    T("list_tasks priority=High",         lambda: chk(len(repo.list_tasks(priority="High")) >= 1))
    T("list_tasks status=Done → empty",   lambda: chk(repo.list_tasks(status="Done") == []))
    repo.update_task(tid, status="In Progress")
    T("update_task status",               lambda: chk(repo.get_task(tid)["status"] == "In Progress"))
    tid2 = repo.add_task(mid, "Aufgabe 2", priority="Critical")
    repo.delete_task(tid2)
    T("delete_task",                      lambda: chk(repo.get_task(tid2) is None))
    return tid


def test_topics(repo: SqliteRepo, mid: int, tid: int) -> None:
    print("\n=== Topics ===")
    topic_id = repo.add_topic(mid, "Integralrechnung", knowledge_level=2)
    T("add_topic returns id",             lambda: chk(isinstance(topic_id, int)))
    T("list_topics count=1",              lambda: chk(len(repo.list_topics(mid)) >= 1))
    repo.update_topic(topic_id, knowledge_level=4)
    T("update_topic level=4",             lambda: chk(repo.list_topics(mid)[0]["knowledge_level"] == 4))
    ks = repo.knowledge_summary(mid)
    T("knowledge_summary keys 0-4",       lambda: chk(all(str(i) in ks for i in range(5))))
    repo.update_topic(topic_id, task_id=tid)
    rows = repo.list_topics(mid)
    T("topic.task_title populated",       lambda: chk(rows[0]["task_title"] is not None))
    repo.delete_topic(topic_id)
    T("delete_topic",                     lambda: chk(len(repo.list_topics(mid)) == 0))


def test_grades(repo: SqliteRepo, mid: int) -> None:
    print("\n=== Grades ===")
    gid = repo.add_grade(mid, "Testat 1", grade=80, max_grade=100, weight=1.0, grade_mode="points")
    T("add_grade returns id",             lambda: chk(isinstance(gid, int)))
    T("list_grades by module",            lambda: chk(len(repo.list_grades(mid)) == 1))
    pct = repo.module_weighted_grade(mid)
    T("weighted_grade 80%",               lambda: chk(abs(pct - 80.0) < 0.01))
    gid2 = repo.add_grade(mid, "Testat 2", grade=4.5, max_grade=6.0, weight=1.0, grade_mode="direct")
    pct2 = repo.module_weighted_grade(mid)
    # direct: (4.5-1)/5=70%; points: 80%; avg=75%
    T("weighted_grade mixed ~75%",        lambda: chk(abs(pct2 - 75.0) < 0.01))
    repo.update_grade(gid, grade=90)
    T("update_grade",                     lambda: chk(any(float(g["grade"]) == 90 for g in repo.list_grades(mid))))
    repo.delete_grade(gid2)
    T("delete_grade",                     lambda: chk(len(repo.list_grades(mid)) == 1))
    gpa = repo.ects_weighted_gpa()
    T("ects_weighted_gpa float or None",  lambda: chk(gpa is None or isinstance(gpa, float)))


def test_events(repo: SqliteRepo, mid: int) -> None:
    print("\n=== Events ===")
    eid = repo.add_event({"title": "Vorlesung", "kind": "study_block",
                          "start_date": "2026-04-01", "end_date": "2026-04-01",
                          "module_id": mid})
    T("add_event returns id",             lambda: chk(isinstance(eid, int)))
    T("list_events >= 1",                 lambda: chk(len(repo.list_events()) >= 1))
    T("event.module_name populated",      lambda: chk(any(e["module_name"] == "Mathematik" for e in repo.list_events())))
    repo.delete_event(eid)
    T("delete_event",                     lambda: chk(all(e["id"] != eid for e in repo.list_events())))


def test_time_logs(repo: SqliteRepo, mid: int) -> None:
    print("\n=== Time Logs ===")
    now_ts = int(_time.time())
    lid = repo.add_time_log(mid, now_ts - 3600, now_ts, 3600, kind="study")
    T("add_time_log returns id",          lambda: chk(isinstance(lid, int)))
    T("list_time_logs all >= 1",          lambda: chk(len(repo.list_time_logs()) >= 1))
    T("list_time_logs by module",         lambda: chk(len(repo.list_time_logs(module_id=mid)) >= 1))
    T("seconds_studied >= 3600",          lambda: chk(repo.seconds_studied_for_module(mid) >= 3600))
    T("get_study_streak >= 1",            lambda: chk(repo.get_study_streak() >= 1))


def test_scraped_data(repo: SqliteRepo, mid: int) -> None:
    print("\n=== Scraped Data ===")
    scraped = {
        "objectives": ["Ziel A", "Ziel B"],
        "content_sections": [{"title": "Kapitel 1", "items": ["Item 1"]}],
        "assessments": [{"art": "Prüfung", "zeitpunkt": "Ende", "weight": 100}],
    }
    repo.save_scraped_data(mid, scraped)
    T("has_scraped_data True",            lambda: chk(repo.has_scraped_data(mid)))
    objs = repo.list_scraped_data(mid, "objective")
    T("objectives count=2",               lambda: chk(len(objs) == 2))
    obj_id = objs[0]["id"]
    repo.set_objective_checked(obj_id, True)
    T("set_objective_checked",            lambda: chk(any(r["checked"] == 1 for r in repo.list_scraped_data(mid, "objective"))))
    repo.reset_objectives_checked(mid)
    T("reset_objectives_checked",         lambda: chk(all(r["checked"] == 0 for r in repo.list_scraped_data(mid, "objective"))))
    repo.delete_scraped_data(mid)
    T("delete_scraped_data",              lambda: chk(not repo.has_scraped_data(mid)))


def test_cascade(repo: SqliteRepo, mid: int) -> None:
    print("\n=== Cascade Delete ===")
    t = repo.add_task(mid, "Cascade-Task")
    repo.add_grade(mid, "Cascade-Grade", grade=50, max_grade=100)
    repo.add_topic(mid, "Cascade-Topic")
    repo.delete_module(mid)
    T("cascade: task gone",               lambda: chk(repo.get_task(t) is None))
    T("cascade: grades gone",             lambda: chk(len(repo.list_grades(mid)) == 0))
    T("cascade: topics gone",             lambda: chk(len(repo.list_topics(mid)) == 0))


def test_exams_analytics(repo: SqliteRepo) -> None:
    print("\n=== Exams & Analytics ===")
    future = (date.today() + timedelta(days=10)).strftime("%Y-%m-%d")
    exam_mid = repo.add_module({"name": "ExamMod", "semester": "3", "ects": 2,
                                 "exam_date": future, "status": "active"})
    T("upcoming_exams in 30d",            lambda: chk(any(m["id"] == exam_mid for m in repo.upcoming_exams(30))))
    T("upcoming_exams in 5d → empty",     lambda: chk(not any(m["id"] == exam_mid for m in repo.upcoming_exams(5))))
    T("all_exams includes mod",           lambda: chk(any(m["id"] == exam_mid for m in repo.all_exams())))
    T("ects_target_hours 2*25=50",        lambda: chk(repo.ects_target_hours(exam_mid) == 50.0))


def run_all() -> None:
    repo, db_path = _make_repo()
    try:
        test_settings(repo)
        mid, mid2 = test_modules(repo)
        tid = test_tasks(repo, mid)
        test_topics(repo, mid, tid)
        test_grades(repo, mid)
        test_events(repo, mid)
        test_time_logs(repo, mid)
        test_scraped_data(repo, mid)
        test_cascade(repo, mid)
        test_exams_analytics(repo)
    finally:
        os.unlink(db_path)

    print(f"\n{'='*50}")
    print(f"  ERGEBNIS: {PASS} passed  |  {FAIL} failed")
    print(f"{'='*50}")
    return FAIL


if __name__ == "__main__":
    sys.exit(run_all())
