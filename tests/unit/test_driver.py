# tests/unit/test_driver.py
import importlib
import sys
import types
from pathlib import Path

import pytest


class _HookList(list):
    def __init__(self, fail_after_append: bool = False) -> None:
        super().__init__()
        self._fail_after_append = fail_after_append

    def append(self, callback) -> None:
        super().append(callback)
        if self._fail_after_append:
            raise RuntimeError("handler registration failed")


class _Timers:
    def __init__(self, fail_after_register: bool = False) -> None:
        self.callbacks: set = set()
        self._fail_after_register = fail_after_register
        self.register_calls = 0
        self.register_kwargs: list[dict] = []

    def register(self, callback, **kwargs) -> None:
        self.register_calls += 1
        self.register_kwargs.append(kwargs)
        self.callbacks.add(callback)
        if self._fail_after_register:
            raise RuntimeError("timer registration failed")

    def is_registered(self, callback) -> bool:
        return callback in self.callbacks

    def unregister(self, callback) -> None:
        self.callbacks.remove(callback)


class _Session:
    def __init__(self) -> None:
        self.stopped = False
        self.stop_calls = 0
        self.cleanup_results = [True]
        self.stop_callbacks: list[tuple] = []
        self.callback_order: list[str] = []

    def stop(self, *callbacks) -> bool:
        self.stopped = True
        self.stop_calls += 1
        self.stop_callbacks.append(callbacks)
        callbacks_complete = True
        for callback in callbacks:
            self.callback_order.append(callback.__name__)
            try:
                callback()
            except Exception:
                callbacks_complete = False
        cleanup_complete = self.cleanup_results.pop(0) if self.cleanup_results else True
        return cleanup_complete and callbacks_complete


def _load_driver(monkeypatch, failure: str, preexisting: bool = False):
    depsgraph = _HookList()
    load_pre = _HookList(fail_after_append=failure == "handler")
    timers = _Timers(fail_after_register=failure == "timer")

    handlers = types.ModuleType("bpy.app.handlers")
    handlers.persistent = lambda callback: callback
    handlers.depsgraph_update_post = depsgraph
    handlers.load_pre = load_pre
    app = types.ModuleType("bpy.app")
    app.__path__ = []
    app.handlers = handlers
    app.timers = timers
    app.version_string = "5.2.0 LTS"
    bpy = types.ModuleType("bpy")
    bpy.__path__ = []
    bpy.app = app
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.setitem(sys.modules, "bpy.app", app)
    monkeypatch.setitem(sys.modules, "bpy.app.handlers", handlers)

    package = types.ModuleType("bridge.blender")
    package.__path__ = [str(Path(__file__).parents[2] / "bridge" / "blender")]
    package.__package__ = "bridge.blender"
    package.register = lambda: None
    package.unregister = lambda: None
    monkeypatch.setitem(sys.modules, "bridge.blender", package)
    monkeypatch.delitem(sys.modules, "bridge.blender.driver", raising=False)
    monkeypatch.delitem(sys.modules, "bridge.blender.scene_reader", raising=False)
    driver = importlib.import_module("bridge.blender.driver")

    session = _Session()

    class _BridgeSession:
        @staticmethod
        def start(*_args, **_kwargs):
            session.stopped = False
            return session

    monkeypatch.setattr(driver, "BridgeSession", _BridgeSession)
    if preexisting:
        depsgraph.append(driver._on_depsgraph)
        load_pre.append(driver._on_load_pre)
        timers.callbacks.add(driver._tick_guard)
    return driver, depsgraph, load_pre, timers, session


def test_driver_wires_load_invalidation_and_ordered_stop_hooks():
    source = (Path(__file__).parents[2] / "bridge" / "blender" / "driver.py").read_text()
    panel_source = (Path(__file__).parents[2] / "bridge" / "blender" / "panel.py").read_text()
    assert "bpy.app.handlers.load_pre.append(_on_load_pre)" in source
    assert "c.bump_generation()" in source
    assert 'else {"CANCELLED"}' in panel_source
    assert "清理未完成，点击重试" in panel_source


def test_registered_load_pre_handler_bumps_the_live_generation(monkeypatch):
    driver, _depsgraph, load_pre, _timers, _session = _load_driver(
        monkeypatch, "none")
    driver.start()
    counter = driver._state["counter"]
    assert counter is not None
    before = counter.generation

    assert load_pre == [driver._on_load_pre]
    load_pre[0](None)

    assert counter.generation == before + 1
    driver._state.update(session=None, counter=None)


def _load_addon(monkeypatch, classes, stop, register_class, unregister_class):
    path = Path(__file__).parents[2] / "bridge" / "blender" / "__init__.py"
    bpy = types.ModuleType("bpy")
    bpy.utils = types.SimpleNamespace(register_class=register_class,
                                      unregister_class=unregister_class)
    driver_module = types.ModuleType("bridge.blender.driver")
    driver_module.stop = stop
    panel_module = types.ModuleType("bridge.blender.panel")
    panel_module.CLASSES = classes
    bridge_package = types.ModuleType("bridge")
    bridge_package.__path__ = [str(path.parents[1])]
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.setitem(sys.modules, "bridge", bridge_package)
    monkeypatch.setitem(sys.modules, "bridge.blender.driver", driver_module)
    monkeypatch.setitem(sys.modules, "bridge.blender.panel", panel_module)
    spec = importlib.util.spec_from_file_location(
        "bridge.blender", path, submodule_search_locations=[str(path.parent)])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "bridge.blender", module)
    spec.loader.exec_module(module)
    return module


def test_addon_unregister_preserves_ui_on_cleanup_failure(monkeypatch):
    classes = (object(), object())
    unregistered = []
    module = _load_addon(monkeypatch, classes, lambda: False, lambda _cls: None,
                         unregistered.append)

    with pytest.raises(RuntimeError, match="cleanup incomplete"):
        module.unregister()
    assert unregistered == []


def test_addon_unregister_is_idempotent(monkeypatch):
    classes = (object(), object())
    registered, unregistered = [], []
    module = _load_addon(monkeypatch, classes, lambda: True, registered.append,
                         unregistered.append)

    module.register()
    module.unregister()
    module.unregister()

    assert registered == list(classes)
    assert unregistered == list(reversed(classes))


def test_addon_register_rolls_back_partial_class_registration(monkeypatch):
    classes = (object(), object())
    registered, unregistered = [], []

    def register_class(cls):
        registered.append(cls)
        if cls is classes[1]:
            raise RuntimeError("injected class register failure")

    module = _load_addon(monkeypatch, classes, lambda: True, register_class,
                         unregistered.append)

    with pytest.raises(RuntimeError, match="injected class register failure"):
        module.register()

    assert registered == list(classes)
    assert unregistered == [classes[0]]
    assert module._registered == []


def test_addon_register_reports_incomplete_class_rollback(monkeypatch):
    classes = (object(), object())
    rollback_failed = True
    unregistered = []

    def register_class(cls):
        if cls is classes[1]:
            raise RuntimeError("injected class register failure")

    def unregister_class(cls):
        unregistered.append(cls)
        if cls is classes[0] and rollback_failed:
            raise RuntimeError("injected rollback failure")

    module = _load_addon(monkeypatch, classes, lambda: True, register_class,
                         unregister_class)

    with pytest.raises(RuntimeError, match="class registration rollback incomplete"):
        module.register()
    assert unregistered == [classes[0]]
    assert module._registered == [classes[0]]

    rollback_failed = False
    module.unregister()
    assert module._registered == []


def test_addon_partial_unregister_failure_is_retryable(monkeypatch):
    classes = (object(), object())
    failed_once = False
    unregistered = []

    def fail_on_first_class_once(cls):
        nonlocal failed_once
        unregistered.append(cls)
        if cls is classes[0] and not failed_once:
            failed_once = True
            raise RuntimeError("injected class unregister failure")

    module = _load_addon(monkeypatch, classes, lambda: True, lambda _cls: None,
                         fail_on_first_class_once)
    module.register()
    with pytest.raises(RuntimeError, match="injected class unregister failure"):
        module.unregister()
    module.unregister()

    assert unregistered == [classes[1], classes[0], classes[0]]


@pytest.mark.parametrize("failure", ["handler", "timer"])
def test_start_registration_failure_rolls_back_without_zombie(monkeypatch, failure):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, failure)

    with pytest.raises(RuntimeError, match=f"{failure} registration failed"):
        driver.start()

    assert depsgraph == [] and load_pre == []
    assert timers.callbacks == set()
    assert session.stopped is True and session.stop_calls == 1
    assert driver._state == {"session": None, "counter": None}


def test_start_preserves_preexisting_hooks_and_does_not_duplicate_timer(monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(
        monkeypatch, "none", preexisting=True)

    driver.start()

    assert depsgraph == [driver._on_depsgraph]
    assert load_pre == [driver._on_load_pre]
    assert timers.callbacks == {driver._tick_guard}
    assert timers.register_calls == 0
    assert driver._state["session"] is session and session.stopped is False
    # Test-only state cleanup; the fake session owns no sockets or threads.
    driver._state.update(session=None, counter=None)


def test_start_self_heals_missing_callbacks_for_live_session(monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, "none")
    driver.start()
    depsgraph.remove(driver._on_depsgraph)
    load_pre.remove(driver._on_load_pre)
    timers.unregister(driver._tick_guard)

    driver.start()

    assert depsgraph == [driver._on_depsgraph]
    assert load_pre == [driver._on_load_pre]
    assert timers.callbacks == {driver._tick_guard}
    assert timers.register_kwargs[-1] == {"first_interval": 0.02, "persistent": True}
    assert session.stop_calls == 0 and driver._state["session"] is session
    driver._state.update(session=None, counter=None)

    for failure, cleanup_results in (("handler", [True]), ("timer", [False, True])):
        driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, "none")
        driver.start()
        depsgraph.remove(driver._on_depsgraph)
        load_pre.remove(driver._on_load_pre)
        timers.unregister(driver._tick_guard)
        load_pre._fail_after_append = failure == "handler"
        timers._fail_after_register = failure == "timer"
        session.cleanup_results = cleanup_results

        with pytest.raises(RuntimeError, match=f"{failure} registration failed"):
            driver.start()

        expected_callbacks = (driver._unregister_timer, driver._unregister_handlers)
        assert session.stop_callbacks == [expected_callbacks]
        assert session.callback_order == ["_unregister_timer", "_unregister_handlers"]
        assert depsgraph == [] and load_pre == [] and timers.callbacks == set()
        assert session.stopped is True and driver.running() is False
        if failure == "handler":
            assert driver._state == {"session": None, "counter": None}
        else:
            assert driver._state["session"] is session
            assert driver.stop() is True
            assert driver._state == {"session": None, "counter": None}


def test_start_state_probe_failure_stops_published_session(monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, "none")

    def fail_probe(_callback):
        raise RuntimeError("timer state probe failed")

    monkeypatch.setattr(timers, "is_registered", fail_probe)
    with pytest.raises(RuntimeError, match="state probe failed"):
        driver.start()

    assert depsgraph == [] and load_pre == []
    assert session.stopped is True and session.stop_calls == 1
    assert driver._state["session"] is session

    monkeypatch.setattr(timers, "is_registered",
                        lambda callback: callback in timers.callbacks)
    assert driver.stop() is True
    assert driver._state == {"session": None, "counter": None}


def test_registration_rollback_retains_session_until_cleanup_retry_succeeds(
        monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, "handler")
    session.cleanup_results = [False, True]

    with pytest.raises(RuntimeError, match="handler registration failed"):
        driver.start()

    assert session.stopped is True and session.stop_calls == 1
    assert driver._state["session"] is session
    assert driver.stop() is True
    assert session.stop_calls == 2
    assert driver._state == {"session": None, "counter": None}


def test_registration_rollback_uses_stop_hooks_and_retains_failed_cleanup(monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, "none")
    session.cleanup_results = [False, True]

    def fail_after_callbacks_escape_local_rollback():
        depsgraph.append(driver._on_depsgraph)
        load_pre.append(driver._on_load_pre)
        timers.callbacks.add(driver._tick_guard)
        raise RuntimeError("callback rollback failed")

    monkeypatch.setattr(driver, "_ensure_callbacks",
                        fail_after_callbacks_escape_local_rollback)
    with pytest.raises(RuntimeError, match="callback rollback failed"):
        driver.start()

    assert session.stop_callbacks[0] == (driver._unregister_timer,
                                         driver._unregister_handlers)
    assert session.callback_order[:2] == ["_unregister_timer", "_unregister_handlers"]
    assert depsgraph == [] and load_pre == [] and timers.callbacks == set()
    assert driver._state["session"] is session and session.stopped is True
    assert driver.stop() is True
    assert driver._state == {"session": None, "counter": None}


def test_disconnect_retains_session_until_cleanup_retry_succeeds(monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, "none")
    driver.start()
    assert driver.stop() is True
    assert session.stop_callbacks[-1] == (driver._unregister_timer,
                                          driver._unregister_handlers)
    assert session.callback_order[-2:] == ["_unregister_timer", "_unregister_handlers"]
    assert depsgraph == [] and load_pre == [] and timers.callbacks == set()

    driver.start()
    session.cleanup_results = [False, False, True]

    assert driver.stop() is False
    assert session.stopped is True and driver._state["session"] is session
    with pytest.raises(RuntimeError, match="cleanup incomplete"):
        driver.start()
    assert driver._state["session"] is session and driver.running() is False

    driver.start()
    assert session.stop_calls == 4
    assert driver._state["session"] is session and driver.running() is True
    driver._state.update(session=None, counter=None)
