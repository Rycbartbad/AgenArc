#!/usr/bin/env python3
"""
euchea - 服务模式启动器

全局监听 Alt+A 热键，触发 PDF→代码 工作流。

用法:
    uv sync --all-extras
    uv run examples/euchea/euchea_serve.py

要求: euchea_serve.py 和 euchea.agrc/ 放在同一目录

API Key 配置（任选一）:
  a. 编辑 ~/.agenarc/config.yaml:
       providers:
         deepseek:
           api_key: sk-your-key
           base_url: https://api.deepseek.com
  b. 或设置环境变量:
       set AGENARC_DEEPSEEK_API_KEY=sk-your-key

退出: 按 Ctrl+C 停止服务
"""

import asyncio
import concurrent.futures
import json
import sys
import threading
from pathlib import Path

# euchea_serve.py 和 euchea.agrc/ 必须在同一目录
_SCRIPT_DIR = Path(__file__).resolve().parent
_BUNDLE_PATH = _SCRIPT_DIR / "euchea.agrc"

# ---- agenarc 模块定位 ----
# 优先：uv 安装版（pyproject.toml 在仓库根目录），回退：手动 sys.path
try:
    from agenarc.engine.executor import ExecutionEngine, ExecutionMode
    from agenarc.operators.builtin import BUILTIN_OPERATORS
    from agenarc.protocol.loader import LoaderError
except ModuleNotFoundError:
    _p = _SCRIPT_DIR
    while _p.parent != _p:
        if (_p / "agenarc").is_dir() and (_p / "agenarc/__init__.py").is_file():
            sys.path.insert(0, str(_p))
            break
        _p = _p.parent
    from agenarc.engine.executor import ExecutionEngine, ExecutionMode
    from agenarc.operators.builtin import BUILTIN_OPERATORS
    from agenarc.protocol.loader import LoaderError


class EucheaService:
    def __init__(self, bundle_path: Path):
        self.bundle_path = bundle_path
        self.engine = None
        self._loop = None
        self._running = False
        self._stop_event = asyncio.Event()

    def _init_engine(self):
        self.engine = ExecutionEngine()
        for nt, oc in BUILTIN_OPERATORS.items():
            if oc:
                self.engine.register_builtin_operator(nt, oc)
        try:
            self.engine.load_protocol(self.bundle_path)
            self.engine.set_bundle_path(self.bundle_path)
        except (LoaderError, ValueError) as e:
            print(f"[euchea] 加载失败: {e}", file=sys.stderr)
            sys.exit(1)
        # 诊断：检查 API key 配置
        from agenarc.config import get_config
        _cfg = get_config()
        _dk = _cfg.get_provider_config("deepseek")
        _have_key = bool(_dk.get("api_key"))
        print(f"[euchea] 引擎已初始化")
        print(f"[euchea] DeepSeek API key: {'已配置' if _have_key else '未配置'}")
        if not _have_key:
            print(f"[euchea] 提示: 请配置 ~/.agenarc/config.yaml 或设 AGENARC_DEEPSEEK_API_KEY 环境变量")

    def _on_hotkey(self):
        if not self._running or self._loop is None:
            return
        print("\n[euchea] ===== Alt+A 触发 =====")
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.engine.execute({}, ExecutionMode.ASYNC), self._loop
            )
            result = future.result(timeout=180)
            if result:
                out = json.dumps(result.final_outputs, default=str, ensure_ascii=False)
                print(f"[euchea] 执行完成 | {out[:300]}")
            else:
                print("[euchea] 执行完成（无输出）")
        except concurrent.futures.TimeoutError:
            print("[euchea] 执行超时（>180s）")
        except Exception as e:
            print(f"[euchea] 执行失败: {e}")

    @staticmethod
    def _run_hotkey_listener(on_hotkey):
        try:
            import keyboard
        except ImportError:
            print("[euchea] 请安装 keyboard: uv pip install keyboard", file=sys.stderr)
            return
        print("[euchea] 监听 Alt+A ...  (Ctrl+C 退出)")
        keyboard.add_hotkey("alt+a", on_hotkey)
        keyboard.wait()

    async def run(self):
        self._init_engine()
        self._running = True
        self._loop = asyncio.get_running_loop()
        t = threading.Thread(target=self._run_hotkey_listener, args=(self._on_hotkey,), daemon=True)
        t.start()
        print(f"[euchea] 服务启动完成")
        print(f"[euchea] 监听 {Path('C:/Users/Admin/Downloads/AA').resolve()}")
        print(f"[euchea] 输出 {Path('C:/Users/Admin/Downloads/AA/project').resolve()}")
        try:
            await self._stop_event.wait()
        except asyncio.CancelledError:
            pass

    async def shutdown(self):
        if not self._running:
            return
        self._running = False
        print("\n[euchea] 正在停止服务...")
        self._stop_event.set()
        print("[euchea] 服务已停止")


def main():
    if not _BUNDLE_PATH.exists():
        print(f"[euchea] 找不到 bundle: {_BUNDLE_PATH}", file=sys.stderr)
        print(f"[euchea] 请确保 euchea_serve.py 和 euchea.agrc/ 在同一目录", file=sys.stderr)
        sys.exit(1)
    svc = EucheaService(_BUNDLE_PATH)
    try:
        asyncio.run(svc.run())
    except KeyboardInterrupt:
        print("\n[euchea] 收到 Ctrl+C")
    except Exception as e:
        print(f"[euchea] 异常退出: {e}", file=sys.stderr)
        sys.exit(1)
    print("[euchea] 再见")


if __name__ == "__main__":
    main()
