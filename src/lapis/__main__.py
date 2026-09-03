from __future__ import annotations

import argparse
import asyncio
import importlib.util
import inspect
import json
import sys

from pathlib import Path
from types import ModuleType

from .context import LapisContext
from .runtime import Runtime, set_context
from .log import debug, info, error
from .config import Config


LOADER_PACKAGE_NAME = "__mainloader__"
LOADER_PACKAGE_DISPLAY_NAME = "Main Loader"


# ============================================================
# Loader Runtime
# ============================================================

def init_loader_runtime() -> LapisContext:
    """初始化 Loader 自己的 Runtime。

    Loader Runtime 不连接 Minecraft Server，
    也不使用 Database。

    它主要用于 Loader 自身的：
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
        package_display_name=LOADER_PACKAGE_DISPLAY_NAME,
        client=None,
        database=None,
        event_registry=None,
    )

    runtime.context = context
    runtime.bind_context(context)

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
    """从指定路径导入 Python Package。

    :raises FileNotFoundError: ``path`` 不存在
    :raises ValueError: ``path`` 不是合法的 Python package 目录
    :raises ImportError: 导入 spec 创建失败或执行模块出错
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
            "Not a valid Python package (missing __init__.py): "
            f"{package_path}\n"
            "         See the README for the required package layout."
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
        f"Loading Package "
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
        f"Package loaded: "
        f"{package_name}"
    )

    return module


# ============================================================
# Package 预检（`lapis check <path>`）
# ============================================================

def _package_json_path(package_dir: Path) -> Path:
    return package_dir / "package.json"


def check_package(
    path: str | Path,
    *,
    verbose: bool = False,
) -> list[str]:
    """预检 package 结构是否合法。

    :returns: 发现的问题列表；空列表表示完全通过。
    """

    problems: list[str] = []
    package_dir = Path(path).resolve()

    def ok(msg: str) -> None:
        if verbose:
            print(f"  [OK]   {msg}")

    def bad(msg: str) -> None:
        problems.append(msg)
        if verbose:
            print(f"  [FAIL] {msg}")

    if verbose:
        print(f"Checking package at: {package_dir}")

    # ---- 目录结构 ----
    if not package_dir.exists():
        problems.append(f"Directory does not exist: {package_dir}")
        return problems

    if not package_dir.is_dir():
        problems.append(f"Path is not a directory: {package_dir}")
        return problems

    init_file = package_dir / "__init__.py"
    if init_file.is_file():
        ok(f"Has __init__.py: {init_file}")
    else:
        bad("Missing __init__.py — Lapis packages must be valid Python packages")

    # ---- package.json（可选但建议）----
    manifest = _package_json_path(package_dir)
    if manifest.is_file():
        ok(f"Has package.json: {manifest}")
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            required_keys = {"package_name"}
            missing = required_keys - data.keys()
            if missing:
                bad(f"package.json missing required keys: {sorted(missing)}")
            else:
                ok("package.json contains package_name")
                if verbose:
                    v = data.get("version", "<unset>")
                    dn = data.get("package_display_name", "<unset>")
                    print(f"         package_name={data['package_name']!r}, "
                          f"version={v!r}, display={dn!r}")
        except json.JSONDecodeError as exc:
            bad(f"package.json is not valid JSON: {exc}")
    else:
        # 可选：不直接算失败，warning 级
        if verbose:
            print(f"  [WARN] No package.json found at {manifest} "
                  "(optional but recommended for publishability)")

    # ---- 可导入性 & main() 暴露 ----
    if init_file.is_file():
        try:
            module = load_package(package_dir)
            ok(f"Import succeeded: {module.__name__}")
        except Exception as exc:  # noqa: BLE001
            bad(f"Failed to import package: {exc!r}")
        else:
            main_fn = getattr(module, "main", None)
            if main_fn is None:
                bad("Module does not expose `main()`. Lapis requires:\n"
                    "         async def main():\n"
                    "             await lapis.start()")
            elif not callable(main_fn):
                bad("`main` attribute exists but is not callable")
            elif not inspect.iscoroutinefunction(main_fn):
                bad("`main()` must be an `async def` coroutine function")
            else:
                ok("Exposes `async def main()`")

    return problems


# ============================================================
# Package Main
# ============================================================

async def run_package(
    module: ModuleType,
) -> None:
    """在 Loader Event Loop 中运行 Package 的 main()。

    Package 必须提供::

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
            f"Package {module.__name__!r} does not define a `main()` coroutine.\n"
            "        Every Lapis package must expose:\n"
            "            from lapis import start"
            "            async def main():\n"
            "                await start()  # usually inside"
        )

    if not callable(main):
        raise TypeError(
            f"{module.__name__}.main exists but is not callable "
            f"(got {type(main).__name__}). It must be an async function."
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
        """初始化 LLoader。

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
        """导入并运行 Package。"""

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
                "Interrupted."
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

def _strip_inline_comment(line: str) -> str:
    """剥离单行 TOML 行内注释（``#`` 之后），保留字符串字面量内的 ``#``。"""

    result = []
    i, n = 0, len(line)
    in_basic = False    # "..."
    in_literal = False  # '...'
    while i < n:
        ch = line[i]
        if in_basic:
            result.append(ch)
            if ch == "\\":
                if i + 1 < n:
                    result.append(line[i + 1])
                    i += 2
                    continue
            elif ch == '"':
                in_basic = False
            i += 1
            continue
        if in_literal:
            result.append(ch)
            if ch == "'":
                in_literal = False
            i += 1
            continue
        # normal
        if ch == "#":
            break
        if ch == '"':
            in_basic = True
        elif ch == "'":
            in_literal = True
        result.append(ch)
        i += 1
    return "".join(result)


def _strip_toml_comments(text: str) -> str:
    """移除 TOML 注释行与行内注释，保留所有配置项与结构。"""

    output = []
    for line in text.split("\n"):
        cleaned = _strip_inline_comment(line).rstrip()
        if cleaned:
            output.append(cleaned)
    return "\n".join(output) + "\n"


def generate_local_config(to_cwd: bool = False) -> int:
    """以包目录下 ``config.toml`` 为模板生成无注释的 ``config.local.toml``。

    :param to_cwd: 为 ``True`` 时写入当前工作目录，否则写入 Lapis 包目录。
    """

    from .config import PACKAGE_DIR
    template = PACKAGE_DIR / "config.toml"
    if not template.is_file():
        error(f"Template config.toml not found: {template}")
        return 1
    text = template.read_text(encoding="utf-8")
    stripped = _strip_toml_comments(text)
    out_dir = Path.cwd() if to_cwd else PACKAGE_DIR
    out_path = out_dir / "config.local.toml"
    out_path.write_text(stripped, encoding="utf-8")
    print(f"Generated: {out_path}")
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m lapis",
        description=(
            "Lapis SDK — the Python companion for the lapis-plugin Minecraft bridge.\n"
            "Run user-developed packages, validate package structure, and more."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m lapis --version\n"
            "  python -m lapis check ./my_package -v\n"
            "  python -m lapis run ./my_package\n"
            "  python -m lapis run ./my_package --debug\n"
            "  python -m lapis debug generate-local-config\n"
            "  python -m lapis debug generate-local-config here\n"
        ),
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"lapis {Config.VERSION}",
        help="Print the Lapis SDK version and exit.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help=(
            "Path to an alternative TOML config file. "
            "Overrides the default $LAPIS_CONFIG_PATH and in-package config.toml."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Force Config.DEBUG = True for this run (overrides config.toml).",
    )

    sub = parser.add_subparsers(
        dest="command",
        metavar="<command>",
        required=True,
    )

    # ---- `run` ----
    p_run = sub.add_parser(
        "run",
        help="Import a Lapis package and execute its `main()` coroutine.",
    )
    p_run.add_argument(
        "path",
        type=str,
        help="Path to the package directory (must contain __init__.py).",
    )

    # ---- `check` ----
    p_check = sub.add_parser(
        "check",
        help="Validate a package's structure without executing user code's runtime side effects.",
    )
    p_check.add_argument(
        "path",
        type=str,
        help="Path to the package directory.",
    )
    p_check.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed per-check results.",
    )

    # ---- `debug` ----
    p_debug = sub.add_parser(
        "debug",
        help="Debug / maintenance utilities.",
    )
    debug_sub = p_debug.add_subparsers(
        dest="debug_command",
        metavar="<debug-command>",
        required=True,
    )
    # ---- `debug generate-local-config` ----
    p_gen = debug_sub.add_parser(
        "generate-local-config",
        help=(
            "Generate a comment-free config.local.toml from the bundled "
            "config.toml template. Default output: lapis package dir; "
            "pass 'here' to write to the current working directory."
        ),
    )
    p_gen.add_argument(
        "where",
        nargs="?",
        choices=["here"],
        default=None,
        help="If 'here', write config.local.toml to the current working directory.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    # ---- 全局参数：--config（在 lapis 包 import 之后才能生效，这里用环境变量）----
    if args.config is not None:
        # CONFIG_PATH 解析在 config.py 加载时已执行；若要覆盖，
        # 必须在 import config 之前设置环境变量。为避免大改加载顺序，
        # 这里仅作为提示信息输出，并在进程级环境变量中设置（如果
        # config.py 还没有在其他地方被加载过的话会生效）。
        os_env_config = args.config
        import os
        os.environ.setdefault("LAPIS_CONFIG_PATH", os_env_config)

    # ---- 全局参数：--debug（即时覆盖 Config.DEBUG）----
    if args.debug:
        Config.DEBUG = True

    # ---- run ----
    if args.command == "run":
        try:
            loader = Loader()
            loader.init()
            loader.run_package(args.path)
        except (FileNotFoundError, ValueError, AttributeError, TypeError, ImportError) as exc:
            error(f"Failed to run package: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001 - 顶-level catch 确保打印
            error(f"Unexpected runtime error: {exc!r}")
            return 2
        return 0

    # ---- check ----
    if args.command == "check":
        problems = check_package(args.path, verbose=args.verbose)
        if not problems:
            if args.verbose:
                print()
            print(f"PASS — package at {args.path!r} looks valid.")
            return 0
        print()
        print(f"FAIL — {len(problems)} problem(s) found:")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
        return 1

    # ---- debug ----
    if args.command == "debug":
        if args.debug_command == "generate-local-config":
            return generate_local_config(to_cwd=(args.where == "here"))
        parser.error(f"Unknown debug command: {args.debug_command!r}")
        return 2

    # argparse 应该已经拦截未知子命令，这里兜底
    parser.error(f"Unknown subcommand: {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
