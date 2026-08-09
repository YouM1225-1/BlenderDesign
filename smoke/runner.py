"""blender --factory-startup --python smoke/runner.py
L3：timer 驱动 tick / revision 递增 / 真场景字段 / **hash scope 盲区真机证明** / 20 次会话循环无泄漏。
正常状态机：每步在一次 timer 回调内完成并立即返回；只有最终失败清理可作有界 wait/sleep
需要 tick 的结果：_tick_guard 与本 runner 同为主线程 timer，回调内阻塞会自饿死（r3 审计）。
结果写 $BLENDERCODEX_SMOKE_OUT（默认 /tmp/bcx_smoke.json），末行打印 SMOKE_{OK,FAIL}。"""
import json
import math
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy  # noqa: E402
import bmesh  # noqa: E402
from bridge.blender import driver, panel  # noqa: E402
from server.core.bridge_client import BridgeClient, BridgeError  # noqa: E402
from smoke.process_registry import (  # noqa: E402
    group_id_is_live,
    new_marker,
    poll_before_deadline,
    scan_records,
    signal_group_id,
    signal_live_records,
)

OUT = os.environ.get("BLENDERCODEX_SMOKE_OUT", "/tmp/bcx_smoke.json")
NFR_OUT = os.environ.get("BLENDERCODEX_NFR_OUT")
RECOVERY_READY = os.environ.get("BLENDERCODEX_RECOVERY_READY")
RECOVERY_STOP = os.environ.get("BLENDERCODEX_RECOVERY_STOP")
LARGE_OBJECTS = max(0, int(os.environ.get("BLENDERCODEX_LARGE_OBJECTS", "0")))
LARGE_BATCH = 1024
LARGE_MAX_WALL_MS = 2000.0       # NFR-P1 candidate on the fixed baseline machine
LARGE_MAX_TICK_MS = 100.0        # 50 ms budget + bounded source step/jitter; not a hard wall
LARGE_QUERY_TIMEOUT = 30.0       # bounded observation window; separate from pass/fail budget
LARGE_QUERY_RUNS = 20            # nearest-rank P95 needs at least twenty observations
NFR_TIMEOUT = 180.0              # 60 calls; observation window, not the <2 s pass threshold
NFR_CLEANUP_MARGIN = 15.0        # single bounded cleanup reserve
NFR_TERM_GRACE = 8.0             # let helper cancellation unwind the SDK Client context
NFR_GROUP_GRACE = 3.0            # emergency TERM window for a recorded MCP process group
RES: dict = {"timer_tick": None, "revision_bump": None, "fields": None,
             "hash_scope": None, "cycles_leak_free": None, "large_scene": None,
             "large_scene_budget_ok": None, "large_scene_metrics": None,
             "nfr_p1": None, "nfr_p1_metrics": None, "errors": []}
ST: dict = {"phase": "start", "box": None, "thread": None, "deadline": 0.0,
            "rev0": -1, "cycle": 0, "base_threads": set(), "run_dir": None,
            "hash_before": None, "hash_after_vertex": None, "large_index": 0,
            "large_mesh": None, "large_query_started": 0.0, "large_build_started": 0.0,
            "large_orig_tick": None, "large_max_tick_ms": 0.0, "large_tick_count": 0,
            "large_max_callback_ms": 0.0, "large_callback_count": 0,
            "large_max_build_callback_ms": 0.0, "large_build_callback_count": 0,
            "large_build_wall_ms": 0.0, "large_query_samples": [],
            "large_observer_samples": [], "large_structural_ok": True,
            "nfr_proc": None, "nfr_error": None, "nfr_process_dir": None,
            "nfr_offline_root": None, "nfr_returncode": None,
            "nfr_registry_marker": None, "nfr_registry_not_before_ns": 0,
            "nfr_registry_pending": False,
            "nfr_known_records": {},
            "nfr_helper_pgid": None, "nfr_work_deadline": 0.0,
            "nfr_final_deadline": 0.0}


def _register():
    for cls in panel.CLASSES:
        bpy.utils.register_class(cls)


def _unregister():
    if not driver.stop():
        raise RuntimeError("bridge cleanup incomplete during smoke")
    for cls in reversed(panel.CLASSES):
        bpy.utils.unregister_class(cls)


def _query_async(timeout: float = 10.0) -> None:
    """在后台线程发起 RPC；结果落在 ST['box']。响应由 GUI timer 驱动的 tick 产生。"""
    s = driver.session()
    box: dict = {}
    deadline = time.monotonic() + timeout
    started = time.perf_counter()

    def call():
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("query deadline expired before worker start")
            box.update(BridgeClient({"socket_path": str(s.socket_path),
                                     "token": s.token}).call("scene_summary",
                                                             timeout=remaining,
                                                             deadline=deadline))
        except BridgeError as e:
            box["__error__"] = str(e)
        except Exception as e:  # verifier thread must always publish a terminal state
            box["__error__"] = f"{type(e).__name__}: {e}"
        finally:
            # The timer poll may run up to its next 100 ms interval after the
            # RPC is done.  Record elapsed time in the worker itself so the
            # product wall-clock metric is not inflated by observer scheduling.
            box["__elapsed_ms"] = (time.perf_counter() - started) * 1000.0

    t = threading.Thread(target=call, daemon=True)
    t.start()
    # The GUI state machine and BridgeClient share the same absolute deadline.
    # A caller must never get a second, fixed 12-second window after the
    # client-side timeout has expired.
    ST.update(box=box, thread=t, deadline=deadline)


def _query_state(phase: str) -> bool | None:
    """Return False while pending, True when complete, or None on failure."""
    thread = ST["thread"]
    if thread.is_alive():
        if time.monotonic() < ST["deadline"]:
            return False
        # Give a just-expired call one bounded scheduling turn.  Never wait
        # without a limit: cleanup must not inherit an unbounded join.
        thread.join(timeout=0.05)
    if thread.is_alive():
        RES["errors"].append(f"{phase}: query deadline exceeded")
        return None
    box = ST["box"]
    if isinstance(box, dict) and "__error__" in box:
        RES["errors"].append(f"{phase}: {box['__error__']}")
        return None
    return True


def _restore_large_tick() -> None:
    original = ST.get("large_orig_tick")
    if original is None:
        return
    try:
        driver.session().tick = original
    finally:
        ST["large_orig_tick"] = None


def _connect_probe() -> bool:
    """建连验证（spec §7.3 循环定义）：能 connect 即证明 listener 活着，不依赖 tick。"""
    s = driver.session()
    try:
        with socket.socket(socket.AF_UNIX) as c:
            c.settimeout(1.0)
            c.connect(str(s.socket_path))
        return True
    except OSError:
        return False


def _close_large_session() -> None:
    _restore_large_tick()
    bpy.ops.bcx.disconnect()
    _unregister()
    ST["phase"] = "cycle"


def _nfr_error_once(message: str) -> None:
    if message not in RES["errors"]:
        RES["errors"].append(message)


def _live_nfr_groups() -> list[int]:
    ST["nfr_registry_pending"] = False
    directory = ST.get("nfr_process_dir")
    marker = ST.get("nfr_registry_marker")
    not_before_ns = ST.get("nfr_registry_not_before_ns")
    known = ST.get("nfr_known_records")
    if not isinstance(known, dict):
        known = {}
        ST["nfr_known_records"] = known
    if (not isinstance(directory, Path) or not directory.exists()
            or not isinstance(marker, str) or type(not_before_ns) is not int):
        ST["nfr_registry_pending"] = True
        message = "nfr process registry identity is missing or unavailable"
        if ST.get("nfr_error") is None:
            ST["nfr_error"] = message
        _nfr_error_once(message)
        return []
    try:
        final_deadline = ST.get("nfr_final_deadline")
        if type(final_deadline) is not float:
            raise RuntimeError("NFR process registry deadline missing")
        records, publishing = scan_records(
            directory, expected_marker=marker, not_before_ns=not_before_ns,
            deadline=final_deadline, known_records=known, retire_dead=False)
        ST["nfr_registry_pending"] = publishing
        return sorted({record.pgid for record in records})
    except Exception as exc:  # evidence failure must fail closed
        ST["nfr_registry_pending"] = True
        message = f"nfr process registry: {type(exc).__name__}: {exc}"
        if ST.get("nfr_error") is None:
            ST["nfr_error"] = message
        _nfr_error_once(message)
        return []


def _nfr_groups_clean(groups: list[int]) -> bool:
    return not groups and ST.get("nfr_registry_pending") is False


def _nfr_registry_is_clean() -> bool:
    return _nfr_groups_clean(_live_nfr_groups())


def _signal_nfr_groups(sig: int) -> None:
    _live_nfr_groups()
    known = ST.get("nfr_known_records")
    if isinstance(known, dict):
        try:
            signal_live_records(known.values(), sig)
        except Exception as exc:
            ST["nfr_registry_pending"] = True
            message = f"nfr process group signal: {type(exc).__name__}: {exc}"
            if ST.get("nfr_error") is None:
                ST["nfr_error"] = message
            _nfr_error_once(message)


def _nfr_helper_is_live() -> bool:
    pgid = ST.get("nfr_helper_pgid")
    return type(pgid) is int and pgid > 1 and group_id_is_live(pgid)


def _signal_nfr_helper(sig: int) -> None:
    pgid = ST.get("nfr_helper_pgid")
    if type(pgid) is int and pgid > 1:
        signal_group_id(pgid, sig)


def _nfr_stage_deadline(seconds: float) -> float:
    return min(ST["nfr_final_deadline"], time.monotonic() + seconds)


def _remove_nfr_process_dir() -> None:
    directory = ST.get("nfr_process_dir")
    if not isinstance(directory, Path) or not directory.exists():
        return
    if any(directory.iterdir()):
        return
    try:
        directory.rmdir()
    except OSError:
        pass


def _settle_nfr(returncode: int | None) -> None:
    artifact = None
    if NFR_OUT:
        try:
            artifact = json.loads(Path(NFR_OUT).read_text())
        except (OSError, ValueError) as exc:
            RES["errors"].append(f"nfr_p1 artifact: {type(exc).__name__}: {exc}")
    metrics = (artifact or {}).get("results") if isinstance(artifact, dict) else None
    final_tick_ms = ST["large_max_tick_ms"]
    large_metrics = RES.get("large_scene_metrics")
    if isinstance(large_metrics, dict):
        large_metrics["max_tick_ms"] = final_tick_ms
        large_metrics["tick_count"] = ST["large_tick_count"]
    RES["large_scene_budget_ok"] = (
        RES.get("large_scene_budget_ok") is True
        and final_tick_ms < LARGE_MAX_TICK_MS
    )
    helper_live = _nfr_helper_is_live()
    live_groups = _live_nfr_groups()
    registry_clean = _nfr_groups_clean(live_groups)
    processes_clean = not helper_live and registry_clean
    if helper_live:
        _nfr_error_once(
            f"nfr leaked helper process group: {ST.get('nfr_helper_pgid')}")
    if not processes_clean:
        if live_groups:
            _nfr_error_once(f"nfr leaked MCP process groups: {live_groups}")
        elif not registry_clean:
            _nfr_error_once("nfr process registry publication did not settle")
    RES["nfr_p1"] = (
        returncode == 0 and ST.get("nfr_error") is None
        and isinstance(artifact, dict) and artifact.get("success") is True
        and RES["large_scene_budget_ok"] is True and processes_clean
    )
    RES["nfr_p1_metrics"] = {
        "results": metrics,
        "max_tick_ms": final_tick_ms,
        "returncode": returncode,
        "processes_clean": processes_clean,
        "helper_group_clean": not helper_live,
        "registry_groups_clean": registry_clean,
    }
    if not RES["nfr_p1"]:
        RES["errors"].append(
            f"nfr_p1 failed: returncode={returncode}, error={ST.get('nfr_error')}, "
            f"artifact_success={(artifact or {}).get('success') if isinstance(artifact, dict) else None}, "
            f"max_tick_ms={final_tick_ms}")
    if not helper_live:
        ST["nfr_helper_pgid"] = None
    _remove_nfr_process_dir()
    _close_large_session()


def _finish() -> None:
    _restore_large_tick()
    nfr_proc = ST.get("nfr_proc")
    final_deadline = ST.get("nfr_final_deadline")
    if nfr_proc is not None and type(final_deadline) is float:
        helper_was_live = _nfr_helper_is_live()
        if final_deadline <= time.monotonic():
            if helper_was_live:
                _signal_nfr_helper(signal.SIGKILL)
                _nfr_error_once("finish: terminated live NFR helper")
            _signal_nfr_groups(signal.SIGKILL)
        else:
            if helper_was_live:
                _signal_nfr_helper(signal.SIGTERM)
                deadline = _nfr_stage_deadline(NFR_TERM_GRACE)
                while _nfr_helper_is_live() and time.monotonic() < deadline:
                    nfr_proc.poll()
                    time.sleep(0.05)
                if _nfr_helper_is_live():
                    _signal_nfr_helper(signal.SIGKILL)
                _nfr_error_once("finish: terminated live NFR helper")
            if not _nfr_registry_is_clean():
                deadline = _nfr_stage_deadline(NFR_GROUP_GRACE)
                while not _nfr_registry_is_clean() and time.monotonic() < deadline:
                    _signal_nfr_groups(signal.SIGTERM)
                    time.sleep(0.05)
            if _nfr_helper_is_live() or not _nfr_registry_is_clean():
                _signal_nfr_helper(signal.SIGKILL)
                deadline = _nfr_stage_deadline(2.0)
                while time.monotonic() < deadline:
                    nfr_proc.poll()
                    _signal_nfr_groups(signal.SIGKILL)
                    if not _nfr_helper_is_live() and _nfr_registry_is_clean():
                        break
                    time.sleep(0.05)
        nfr_proc.poll()
        if _nfr_helper_is_live():
            _nfr_error_once(
                f"finish: unreaped helper process group: {ST['nfr_helper_pgid']}")
        groups = _live_nfr_groups()
        if not _nfr_groups_clean(groups):
            _nfr_error_once(f"finish: unreaped MCP process groups: {groups}")
    _remove_nfr_process_dir()
    thread = ST.get("thread")
    if thread is not None and thread.is_alive():
        thread.join(timeout=0.25)
        if thread.is_alive():
            RES["errors"].append("finish: query thread did not settle")
    keys = ("timer_tick", "revision_bump", "fields", "hash_scope", "cycles_leak_free")
    if LARGE_OBJECTS:
        keys += ("large_scene", "large_scene_budget_ok")
    if NFR_OUT:
        keys += ("nfr_p1",)
    ok = all(RES[k] is True for k in keys) and not RES["errors"]
    Path(OUT).write_text(json.dumps(RES, ensure_ascii=False, indent=1))
    print("SMOKE_OK" if ok else f"SMOKE_FAIL {RES}")
    bpy.ops.wm.quit_blender()


def _step() -> float | None:
    ph = ST["phase"]
    try:
        if ph == "start":
            ST["base_threads"] = {
                thread for thread in threading.enumerate()
                if thread.name == "bcx-io" and thread.is_alive()
            }
            _register()
            bpy.ops.bcx.allow_connect()
            _query_async()                       # 只有 GUI timer 在驱动 tick
            ST["phase"] = "wait1"
        elif ph in ("wait1", "wait2", "wait_vertex", "wait_moved"):
            state = _query_state(ph)
            if state is False:
                return 0.1                       # 关键：让出主线程给 _tick_guard
            if state is None:
                _finish()
                return None
            box = ST["box"]
            if ph == "wait1":
                RES["timer_tick"] = box.get("scene_name") is not None
                ST["rev0"] = box.get("scene_revision", -1)
                bpy.ops.mesh.primitive_cube_add()  # GUI 下触发 depsgraph handler
                _query_async()
                ST["phase"] = "wait2"
            elif ph == "wait2":
                RES["revision_bump"] = box.get("scene_revision", -1) > ST["rev0"]
                summary = box.get("summary", {})
                RES["fields"] = (summary.get("object_count") == 4
                                 and summary.get("mesh_count") == 2
                                 and summary.get("camera_count") == 1
                                 and summary.get("light_count") == 1
                                 and box.get("scene_hash", "").startswith("sha256:")
                                 and box.get("units", {}).get("system")
                                 in ("METRIC", "NONE"))
                # ---- hash scope 真机证明（复审 F-05）：v1 覆盖 transform、
                #      不覆盖顶点。纯函数测试无法证明这一点，只能在真 Blender 做 ----
                ST["hash_before"] = box.get("scene_hash")
                obj = bpy.context.active_object          # 上一步新增的 Cube
                bpy.ops.object.mode_set(mode="EDIT")
                mesh = bmesh.from_edit_mesh(obj.data)
                mesh.verts.ensure_lookup_table()
                mesh.verts[0].co.x += 0.5                # 真 Edit Mode 顶点编辑
                bmesh.update_edit_mesh(obj.data)
                bpy.ops.object.mode_set(mode="OBJECT")
                _query_async()
                ST["phase"] = "wait_vertex"
            elif ph == "wait_vertex":
                ST["hash_after_vertex"] = box.get("scene_hash")
                bpy.context.active_object.location.x += 1.0   # 对象级 transform
                _query_async()
                ST["phase"] = "wait_moved"
            else:   # wait_moved
                hash_moved = box.get("scene_hash")
                RES["hash_scope"] = (
                    ST["hash_before"] == ST["hash_after_vertex"]   # 顶点：不可见
                    and ST["hash_after_vertex"] != hash_moved      # transform：可见
                )
                if not RES["hash_scope"]:
                    RES["errors"].append(
                        f"hash_scope: before={ST['hash_before']} "
                        f"vertex={ST['hash_after_vertex']} moved={hash_moved}")
                if LARGE_OBJECTS:
                    for old in list(bpy.data.objects):
                        bpy.data.objects.remove(old, do_unlink=True)
                    mesh = bpy.data.meshes.new("LargeSharedMesh")
                    mesh.from_pydata(
                        [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                         (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)],
                        [], [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
                             (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)],
                    )
                    ST.update(phase="large_build", large_mesh=mesh,
                              large_index=0, large_build_started=time.perf_counter())
                else:
                    bpy.ops.bcx.disconnect()
                    _unregister()
                    ST["phase"] = "cycle"
        elif ph == "large_build":
            mesh = ST["large_mesh"]
            scene = bpy.context.scene
            start = ST["large_index"]
            stop = min(start + LARGE_BATCH, LARGE_OBJECTS)
            for index in range(start, stop):
                obj = bpy.data.objects.new(f"Large{index:06d}", mesh)
                scene.collection.objects.link(obj)
            ST["large_index"] = stop
            if stop < LARGE_OBJECTS:
                return 0.01
            bpy.context.view_layer.update()
            session = driver.session()
            original_tick = session.tick
            ST["large_orig_tick"] = original_tick

            def measured_tick(budget_ms=50):
                started = time.perf_counter()
                try:
                    return original_tick(budget_ms)
                finally:
                    ST["large_tick_count"] += 1
                    ST["large_max_tick_ms"] = max(
                        ST["large_max_tick_ms"],
                        (time.perf_counter() - started) * 1000.0,
                    )

            session.tick = measured_tick
            ST["large_build_wall_ms"] = (
                time.perf_counter() - ST["large_build_started"]) * 1000.0
            ST["large_query_started"] = time.perf_counter()
            # Keep the observation timeout distinct from the 2 s pass/fail
            # budget so an over-budget result still emits useful metrics.  The
            # client and GUI state machine share this one bounded deadline.
            _query_async(timeout=LARGE_QUERY_TIMEOUT)
            ST["phase"] = "large_wait"
        elif ph == "large_wait":
            state = _query_state(ph)
            if state is False:
                return 0.1
            if state is None:
                _finish()
                return None
            box = ST["box"]
            summary = box.get("summary", {})
            wall_ms = box.get("__elapsed_ms")
            if not isinstance(wall_ms, (int, float)):
                raise RuntimeError("large query elapsed metric missing")
            observer_wall_ms = (time.perf_counter() - ST["large_query_started"]) * 1000.0
            structural_this_run = (
                summary.get("object_count") == LARGE_OBJECTS
                and summary.get("mesh_count") == LARGE_OBJECTS
                and summary.get("camera_count") == 0
                and summary.get("light_count") == 0
            )
            ST["large_structural_ok"] = (
                ST["large_structural_ok"] and structural_this_run)
            ST["large_query_samples"].append(float(wall_ms))
            ST["large_observer_samples"].append(observer_wall_ms)
            if len(ST["large_query_samples"]) < LARGE_QUERY_RUNS:
                ST["large_query_started"] = time.perf_counter()
                _query_async(timeout=LARGE_QUERY_TIMEOUT)
                return 0.01

            ordered = sorted(ST["large_query_samples"])
            p95_index = math.ceil(0.95 * len(ordered)) - 1
            query_p95_ms = ordered[p95_index]
            observer_ordered = sorted(ST["large_observer_samples"])
            observer_p95_ms = observer_ordered[p95_index]
            metrics = {
                "target_objects": LARGE_OBJECTS,
                "object_count": summary.get("object_count"),
                "mesh_count": summary.get("mesh_count"),
                "camera_count": summary.get("camera_count"),
                "light_count": summary.get("light_count"),
                "build_wall_ms": ST["large_build_wall_ms"],
                "query_runs": len(ordered),
                "query_wall_ms": query_p95_ms,
                "query_wall_ms_p95": query_p95_ms,
                "query_wall_ms_max": ordered[-1],
                "query_wall_ms_samples": ST["large_query_samples"],
                "observer_wall_ms_p95": observer_p95_ms,
                "observer_wall_ms_max": observer_ordered[-1],
                "max_tick_ms": ST["large_max_tick_ms"],
                "tick_count": ST["large_tick_count"],
                "max_callback_ms": ST["large_max_callback_ms"],
                "callback_count": ST["large_callback_count"],
                "max_build_callback_ms": ST["large_max_build_callback_ms"],
                "build_callback_count": ST["large_build_callback_count"],
            }
            RES["large_scene_metrics"] = metrics
            structural_ok = ST["large_structural_ok"]
            RES["large_scene"] = structural_ok
            RES["large_scene_budget_ok"] = (
                structural_ok and query_p95_ms < LARGE_MAX_WALL_MS
                and ST["large_max_tick_ms"] < LARGE_MAX_TICK_MS
            )
            if not structural_ok:
                RES["errors"].append(f"large_scene: {metrics}")
            elif not RES["large_scene_budget_ok"]:
                RES["errors"].append(f"large_scene budget: {metrics}")
            if NFR_OUT:
                session = driver.session()
                root = session.session_dir.parents[1]
                process_dir = Path(str(NFR_OUT) + ".processes")
                process_dir.mkdir(mode=0o700)
                os.chmod(process_dir, 0o700)
                offline_root = Path(str(NFR_OUT) + ".offline-root")
                offline_root.mkdir(mode=0o700)
                os.chmod(offline_root, 0o700)
                registry_marker = new_marker()
                registry_not_before_ns = time.monotonic_ns()
                ST["nfr_process_dir"] = process_dir
                ST["nfr_offline_root"] = offline_root
                ST["nfr_registry_marker"] = registry_marker
                ST["nfr_registry_not_before_ns"] = registry_not_before_ns
                command = [
                    "/Users/yeminjie/.local/bin/uv", "run", "--frozen", "python",
                    "smoke/e2e.py", "nfr", "--root", str(root),
                    "--instance", session.instance_id, "--output", NFR_OUT,
                    "--process-registry", str(process_dir),
                    "--offline-root", str(offline_root),
                    "--timeout-seconds", str(NFR_TIMEOUT - NFR_CLEANUP_MARGIN),
                    "--registry-marker", registry_marker,
                    "--registry-not-before-ns", str(registry_not_before_ns),
                ]
                spawned_at = time.monotonic()
                process = subprocess.Popen(
                    command, cwd=Path(__file__).resolve().parents[1],
                    start_new_session=True)
                work_deadline = spawned_at + NFR_TIMEOUT - NFR_CLEANUP_MARGIN
                final_deadline = spawned_at + NFR_TIMEOUT
                ST.update(
                    nfr_proc=process,
                    nfr_helper_pgid=process.pid,
                    nfr_work_deadline=work_deadline,
                    nfr_final_deadline=final_deadline,
                    phase="nfr_wait",
                    deadline=work_deadline,
                )
            else:
                _close_large_session()
        elif ph == "nfr_wait":
            proc = ST["nfr_proc"]
            returncode, deadline_expired = poll_before_deadline(
                proc.poll, ST["nfr_work_deadline"])
            if deadline_expired:
                ST["nfr_error"] = "NFR helper deadline exceeded"
                _signal_nfr_helper(signal.SIGTERM)
                ST.update(phase="nfr_helper_term",
                          deadline=_nfr_stage_deadline(NFR_TERM_GRACE))
            elif returncode is not None:
                ST["nfr_returncode"] = returncode
                groups = _live_nfr_groups()
                if _nfr_helper_is_live() or not _nfr_groups_clean(groups):
                    _signal_nfr_helper(signal.SIGTERM)
                    _signal_nfr_groups(signal.SIGTERM)
                    ST.update(phase="nfr_group_term",
                              deadline=_nfr_stage_deadline(NFR_GROUP_GRACE))
                else:
                    _settle_nfr(returncode)
            else:
                return 0.05
        elif ph == "nfr_helper_term":
            proc = ST["nfr_proc"]
            returncode = proc.poll()
            if returncode is not None and ST.get("nfr_returncode") is None:
                ST["nfr_returncode"] = returncode
            if returncode is not None and not _nfr_helper_is_live():
                if not _nfr_registry_is_clean():
                    _signal_nfr_groups(signal.SIGTERM)
                    ST.update(phase="nfr_group_term",
                              deadline=_nfr_stage_deadline(NFR_GROUP_GRACE))
                else:
                    _settle_nfr(ST.get("nfr_returncode"))
            elif time.monotonic() < ST["deadline"]:
                return 0.05
            else:
                _signal_nfr_helper(signal.SIGKILL)
                _signal_nfr_groups(signal.SIGTERM)
                ST.update(phase="nfr_group_term",
                          deadline=_nfr_stage_deadline(NFR_GROUP_GRACE))
        elif ph == "nfr_group_term":
            proc = ST["nfr_proc"]
            returncode = proc.poll()
            if returncode is not None and ST.get("nfr_returncode") is None:
                ST["nfr_returncode"] = returncode
            groups = _live_nfr_groups()
            if (returncode is not None and not _nfr_helper_is_live()
                    and _nfr_groups_clean(groups)):
                _settle_nfr(ST.get("nfr_returncode"))
            elif time.monotonic() < ST["deadline"]:
                _signal_nfr_groups(signal.SIGTERM)
                return 0.05
            else:
                _signal_nfr_helper(signal.SIGKILL)
                _signal_nfr_groups(signal.SIGKILL)
                ST.update(phase="nfr_reap", deadline=_nfr_stage_deadline(2.0))
        elif ph == "nfr_reap":
            proc = ST["nfr_proc"]
            returncode = proc.poll()
            if returncode is not None and ST.get("nfr_returncode") is None:
                ST["nfr_returncode"] = returncode
            groups = _live_nfr_groups()
            if (returncode is not None and not _nfr_helper_is_live()
                    and _nfr_groups_clean(groups)):
                saved = ST.get("nfr_returncode")
                _settle_nfr(returncode if saved is None else saved)
            elif time.monotonic() < ST["deadline"]:
                _signal_nfr_groups(signal.SIGKILL)
                return 0.05
            else:
                if _nfr_helper_is_live():
                    _nfr_error_once(
                        "nfr unreaped helper process group: "
                        f"{ST.get('nfr_helper_pgid')}")
                groups = _live_nfr_groups()
                if groups:
                    _nfr_error_once(f"nfr unreaped MCP process groups: {groups}")
                _settle_nfr(ST.get("nfr_returncode"))
        elif ph == "cycle":                       # 每次回调跑一整圈会话循环
            _register()
            bpy.ops.bcx.allow_connect()
            s = driver.session()
            ST["run_dir"] = s.session_dir.parent
            assert s.socket_path.exists() and _connect_probe()
            bpy.ops.bcx.disconnect()
            _unregister()
            ST["cycle"] += 1
            if ST["cycle"] >= 20:
                ST.update(phase="settle", deadline=time.monotonic() + 1.0)
        elif ph == "settle":                      # 留 1 秒让 join 完的线程退场
            if time.monotonic() < ST["deadline"]:
                return 0.1
            leaked = [
                thread for thread in threading.enumerate()
                if thread.name == "bcx-io" and thread.is_alive()
                and thread not in ST["base_threads"]
            ]
            run_dir = ST["run_dir"]
            leftover = (list(run_dir.glob("gui-*"))
                        if run_dir and run_dir.exists() else [])
            RES["cycles_leak_free"] = leaked == [] and leftover == []
            if not RES["cycles_leak_free"]:
                thread_names = [f"{thread.name}:{thread.ident}" for thread in leaked]
                RES["errors"].append(
                    f"leaked_threads={thread_names}, leftover={leftover}")
            _finish()
            return None
    except Exception as e:  # noqa: BLE001
        RES["errors"].append(f"{ph}: {type(e).__name__}: {e}")
        _finish()
        return None
    return 0.05


def _timed_step():
    phase = ST["phase"]
    started = time.perf_counter()
    try:
        return _step()
    finally:
        if LARGE_OBJECTS and phase == "large_wait":
            ST["large_callback_count"] += 1
            ST["large_max_callback_ms"] = max(
                ST["large_max_callback_ms"],
                (time.perf_counter() - started) * 1000.0,
            )
        elif LARGE_OBJECTS and phase == "large_build":
            ST["large_build_callback_count"] += 1
            ST["large_max_build_callback_ms"] = max(
                ST["large_max_build_callback_ms"],
                (time.perf_counter() - started) * 1000.0,
            )


def _recovery_step() -> float | None:
    try:
        if ST["phase"] == "start":
            _register()
            bpy.ops.bcx.allow_connect()
            session = driver.session()
            if session is None:
                raise RuntimeError("recovery session failed to start")
            ready = Path(RECOVERY_READY)
            temporary = ready.with_suffix(ready.suffix + ".tmp")
            temporary.write_text(json.dumps({
                "instance_id": session.instance_id,
                "pid": os.getpid(),
            }))
            os.replace(temporary, ready)
            ST["phase"] = "recovery_wait"
        elif ST["phase"] == "recovery_wait" and Path(RECOVERY_STOP).exists():
            bpy.ops.bcx.disconnect()
            _unregister()
            bpy.ops.wm.quit_blender()
            return None
    except Exception as exc:  # noqa: BLE001
        print(f"RECOVERY_FAIL {type(exc).__name__}: {exc}")
        bpy.ops.wm.quit_blender()
        return None
    return 0.05


if bool(RECOVERY_READY) != bool(RECOVERY_STOP):
    raise RuntimeError("recovery mode requires both ready and stop paths")
if RECOVERY_READY:
    bpy.app.timers.register(_recovery_step, first_interval=0.5)
else:
    bpy.app.timers.register(_timed_step, first_interval=0.5)
