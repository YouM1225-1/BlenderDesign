"""blender --background --factory-startup --python smoke/bg_check.py
退出码 0 = Bridge 启停与 ping 往返在真 bpy 下成立。"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge.blender import driver  # noqa: E402
from server.core.bridge_client import BridgeClient  # noqa: E402

driver.start()
s = driver.session()
assert s is not None and s.socket_path.exists()

result: dict = {}
t = threading.Thread(target=lambda: result.update(
    BridgeClient({"socket_path": str(s.socket_path), "token": s.token}).call("ping")))
t.start()
t0 = time.monotonic()
while t.is_alive() and time.monotonic() - t0 < 10.0:   # 限时泵：空队列 tick 微秒级返回，
    time.sleep(s.tick(50))                             # 必须 sleep 让客户端线程有机会跑
t.join(timeout=1)
assert result.get("instance_id") == s.instance_id, result
assert result.get("blender_version") == "5.2.0", result

driver.stop()
assert not s.socket_path.exists()
print("BG_CHECK_OK")
