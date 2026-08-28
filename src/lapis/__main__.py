from __future__ import annotations

import sys
import asyncio
import importlib.util

from pathlib import Path
from types import ModuleType

from .context import LapisContext
from .runtime import Runtime, set_context
from .log import debug, info, error


LOADER_PACKAGE_NAME = "__lapis_loader__"


# ============================================================
# Loader Runtime
# ============================================================

def init_loader_runtime() -> LapisContext:
    """
    初始化 LLoader 自己的 Runtime。

    Loader Runtime 不连接 Minecraft Server，
    也不使用 Database。

    它主要用于 LLoader 自身的：
        - 日志
        - 配置
        - Package 管理
        - Event Loop
        - 其他 Loader 功能
    """

    runtime = Runtime(
        LOADER_PACKAGE_NAME
    )

    context = LapisContext(
        package_name=LOADER_PACKAGE_NAME,
        client=None,
        database=None,
        event_registry=None,
    )

    runtime.context = context

    set_context(context)

    debug(
        f"Initialized Loader Runtime: "
        f"{LOADER_PACKAGE_NAME}"
    )

    return context


# ============================================================
# Package Loader
# ============================================================

def load_package(
    path: str | Path,
) -> ModuleType:
    """
    从指定路径导入 PythonMod。

    path 必须是一个 Python package，例如：

        ./mypkg/

    且其中存在：

        ./mypkg/__init__.py
    """

    package_path = Path(
        path
    ).resolve()

    if not package_path.exists():
        raise FileNotFoundError(
            f"Package path does not exist: "
            f"{package_path}"
        )

    if not package_path.is_dir():
        raise ValueError(
            f"Package path must be a directory: "
            f"{package_path}"
        )

    init_file = (
        package_path / "__init__.py"
    )

    if not init_file.is_file():
        raise ValueError(
            f"Not a Python package "
            f"(missing __init__.py): "
            f"{package_path}"
        )

    package_name = package_path.name

    spec = (
        importlib.util
        .spec_from_file_location(
            package_name,
            init_file,
            submodule_search_locations=[
                str(package_path)
            ],
        )
    )

    if spec is None:
        raise ImportError(
            f"Cannot create import spec "
            f"for {package_path}"
        )

    if spec.loader is None:
        raise ImportError(
            f"Cannot find loader "
            f"for {package_path}"
        )

    module = (
        importlib.util.module_from_spec(
            spec
        )
    )

    # 必须提前加入 sys.modules。
    #
    # 否则 package 内部的：
    #
    #     from .xxx import ...
    #
    # 以及：
    #
    #     import mypkg.xxx
    #
    # 可能无法正常工作。
    sys.modules[
        package_name
    ] = module

    debug(
        f"Loading PythonMod "
        f"{package_name!r} "
        f"from {package_path}"
    )

    try:
        spec.loader.exec_module(
            module
        )

    except Exception:
        sys.modules.pop(
            package_name,
            None,
        )
        raise

    info(
        f"PythonMod loaded: "
        f"{package_name}"
    )

    return module


# ============================================================
# Package Main
# ============================================================

async def run_package(
    module: ModuleType,
) -> None:
    """
    在 Loader Event Loop 中运行 Package 的 main()。

    Package 必须提供：

        async def main():
            ...
    """

    main = getattr(
        module,
        "main",
        None,
    )

    if main is None:
        raise AttributeError(
            f"Package {module.__name__!r} "
            "does not define main()"
        )

    if not callable(main):
        raise TypeError(
            f"{module.__name__}.main "
            "is not callable"
        )

    info(
        f"Starting Package: "
        f"{module.__name__}"
    )

    # main() 必须是 async function。
    #
    # 这里不会执行 asyncio.run()。
    #
    # 当前函数本身就在 Loader Event Loop
    # 中运行，因此直接 await 即可。
    await main()


# ============================================================
# Loader
# ============================================================

class Loader:

    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        self.context: LapisContext | None = None

    def init(self):
        """
        初始化 LLoader。

        创建：
            1. Loader Runtime
            2. Loader Event Loop
        """

        self.context = (
            init_loader_runtime()
        )

        self.loop = (
            asyncio.new_event_loop()
        )

        asyncio.set_event_loop(
            self.loop
        )

        debug(
            "Loader event loop initialized"
        )

    def run_package(
        self,
        path: str | Path,
    ) -> None:
        """
        导入并运行 Package。
        """

        if self.loop is None:
            raise RuntimeError(
                "Loader has not been initialized"
            )

        # ----------------------------------------------------
        # Package import 是同步操作。
        #
        # 这里先导入 package。
        #
        # import 过程中：
        #
        #     lapis.init(...)
        #
        # 会创建 Package Runtime。
        # ----------------------------------------------------

        module = load_package(
            path
        )

        # ----------------------------------------------------
        # 创建 Package main coroutine。
        #
        # 注意这里不会执行 main。
        # ----------------------------------------------------

        coroutine = run_package(
            module
        )

        # ----------------------------------------------------
        # 将 coroutine 放入 Loader Event Loop。
        # ----------------------------------------------------

        task = self.loop.create_task(
            coroutine,
            name=f"package:{module.__name__}",
        )

        # ----------------------------------------------------
        # 启动 Event Loop。
        #
        # 由于 task 本身通常是一个长期运行任务，
        # Event Loop 会持续运行。
        # ----------------------------------------------------

        try:

            self.loop.run_until_complete(
                task
            )

        except KeyboardInterrupt:

            info(
                "Loader interrupted."
            )

            task.cancel()

            # 等待 task 正常结束，
            # 避免产生：
            #
            #     Task was destroyed but pending
            #
            try:
                self.loop.run_until_complete(
                    task
                )

            except asyncio.CancelledError:
                pass

        finally:

            # ------------------------------------------------
            # 取消剩余任务
            # ------------------------------------------------

            pending = asyncio.all_tasks(
                self.loop
            )

            for pending_task in pending:
                pending_task.cancel()

            if pending:
                self.loop.run_until_complete(
                    asyncio.gather(
                        *pending,
                        return_exceptions=True,
                    )
                )

            # ------------------------------------------------
            # 关闭 async generators
            # ------------------------------------------------

            self.loop.run_until_complete(
                self.loop.shutdown_asyncgens()
            )

            # ------------------------------------------------
            # 关闭 Event Loop
            # ------------------------------------------------

            self.loop.close()

            asyncio.set_event_loop(
                None
            )

            debug(
                "Loader event loop closed"
            )


# ============================================================
# CLI
# ============================================================

def print_usage():
    print(
        "Usage:\n"
        "    python -m lapis run <path>"
    )


def main():

    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]

    if command != "run":

        error(
            f"Unknown command: "
            f"{command!r}"
        )

        print_usage()
        raise SystemExit(1)

    if len(sys.argv) != 3:

        print_usage()
        raise SystemExit(1)

    package_path = sys.argv[2]

    loader = Loader()
    loader.init()
    loader.run_package(
        package_path
    )


if __name__ == "__main__":
    main()