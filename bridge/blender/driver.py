"""timer/handler 注册与 tick 护栏。§3.6 护栏、§8.1：timer persistent=True，handler 必须 @persistent。"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import bpy
from bpy.app.handlers import persistent

from ..core.lifecycle import BridgeSession
from ..core.queue import IDLE_INTERVAL
from .scene_reader import BpySceneReader, RevisionCounter

_diag = logging.getLogger("bcx.bridge")
_state: dict = {"session": None, "counter": None}


def _runtime_root() -> Path:
    env = os.environ.get("BLENDERCODEX_ROOT")
    return Path(env) if env else Path.home() / "Library" / "Application Support" / "BlenderCodex"


@persistent
def _on_depsgraph(scene, depsgraph=None) -> None:   # 只自增，不算 hash（R-P0-10）
    c = _state["counter"]
    if c is not None:
        c.bump()


@persistent
def _on_load_pre(_filepath) -> None:
    """在 Blender 释放旧 bpy data 前使跨 tick snapshot continuation 失效。"""
    c = _state["counter"]
    if c is not None:
        c.bump_generation()


def _tick_guard() -> float | None:                  # §3.6：护栏不可省略
    s = _state["session"]
    if s is None or s.stopped:
        return None                                  # 会话没了 → timer 自然注销
    try:
        return s.tick(50)
    except Exception:
        _diag.exception("tick failed")
        return 0.1


def _ensure_callbacks() -> None:
    """Register missing persistent callbacks, rolling back this attempt on failure."""
    depsgraph_was_registered = load_pre_was_registered = timer_was_registered = True
    try:
        depsgraph_was_registered = _on_depsgraph in bpy.app.handlers.depsgraph_update_post
        load_pre_was_registered = _on_load_pre in bpy.app.handlers.load_pre
        timer_was_registered = bpy.app.timers.is_registered(_tick_guard)
        if not depsgraph_was_registered:
            bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
        if not load_pre_was_registered:
            bpy.app.handlers.load_pre.append(_on_load_pre)
        if not timer_was_registered:
            bpy.app.timers.register(_tick_guard, first_interval=IDLE_INTERVAL, persistent=True)
    except BaseException:
        # Roll back only callbacks added by this attempt; preserve pre-existing ones.
        try:
            if not timer_was_registered and bpy.app.timers.is_registered(_tick_guard):
                bpy.app.timers.unregister(_tick_guard)
        except Exception:
            _diag.exception("failed to roll back timer registration")
        for handlers, callback, was_registered in (
            (bpy.app.handlers.load_pre, _on_load_pre, load_pre_was_registered),
            (bpy.app.handlers.depsgraph_update_post, _on_depsgraph,
             depsgraph_was_registered),
        ):
            try:
                if not was_registered and callback in handlers:
                    handlers.remove(callback)
            except Exception:
                _diag.exception("failed to roll back handler registration")
        raise


def start() -> None:
    existing = _state["session"]
    if existing is not None:
        if existing.stopped:
            if not existing.stop(_unregister_timer, _unregister_handlers):
                raise RuntimeError("previous session cleanup incomplete; retry disconnect")
            _state.update(session=None, counter=None)
        else:
            _ensure_callbacks()  # self-heal after a persistent reload drops a callback
            return
    counter = RevisionCounter()
    reader = BpySceneReader(counter)
    session = BridgeSession.start(_runtime_root(), reader,
                                  blender_version=reader.blender_version())
    try:
        _state.update(session=session, counter=counter)
        _ensure_callbacks()
    except BaseException:
        try:
            cleanup_complete = session.stop(_unregister_timer, _unregister_handlers)
        except Exception:
            _diag.exception("failed to stop session during registration rollback")
            cleanup_complete = False
        if cleanup_complete:
            _state.update(session=None, counter=None)
        raise


def _unregister_timer() -> None:
    if bpy.app.timers.is_registered(_tick_guard):    # §3.7 步 6（driver 层职责）
        bpy.app.timers.unregister(_tick_guard)


def _unregister_handlers() -> None:
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:   # 步 7
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    if _on_load_pre in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_on_load_pre)


def stop() -> bool:
    session = _state["session"]
    if session is None:
        return True
    complete = session.stop(_unregister_timer, _unregister_handlers)
    if complete:
        _state.update(session=None, counter=None)
    return complete


def running() -> bool:
    current = _state["session"]
    return current is not None and not current.stopped


def session() -> BridgeSession | None:
    return _state["session"]
