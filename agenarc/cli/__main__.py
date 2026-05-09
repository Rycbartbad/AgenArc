"""
AgenArc CLI

Command-line interface for AgenArc execution engine.

Usage:
    agenarc run <agent.agrc|flow.json>
    agenarc shell <agent.agrc|flow.json>
    agenarc validate <agent.agrc|flow.json>
    agenarc info <agent.agrc|flow.json>
    agenarc pack <directory> [output.agrc]
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from agenarc import __version__

# Import all command functions and helpers from the commands package
from agenarc.cli.commands import (  # noqa: F401
    InteractiveREPL,
    command_run,
    command_shell,
    command_serve,
    command_validate,
    command_info,
    command_visualize,
    _install_bundle_plugins,
    _extract_agrc,
    _resolve_bundle_path,
    pack_bundle,
    print_error,
    print_success,
)


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="agenarc",
        description="Directed-graph Agent Orchestration Engine"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"agenarc {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run command
    run_parser = subparsers.add_parser(
        "run",
        help="Execute an agent (.agrc or .json)"
    )
    run_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )
    run_parser.add_argument(
        "--input",
        "-i",
        type=str,
        help="Initial input as JSON string"
    )
    run_parser.add_argument(
        "--mode",
        "-m",
        choices=["sync", "async", "parallel"],
        default="async",
        help="Execution mode"
    )
    run_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    # serve command (service mode with event plugins)
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start agent as a background service with event plugins"
    )
    serve_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )
    serve_parser.add_argument(
        "--mode",
        "-m",
        choices=["sync", "async", "parallel"],
        default="async",
        help="Execution mode"
    )
    serve_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate an agent bundle or protocol"
    )
    validate_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )

    # info command
    info_parser = subparsers.add_parser(
        "info",
        help="Show agent/protocol information"
    )
    info_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )

    # pack command
    pack_parser = subparsers.add_parser(
        "pack",
        help="Pack a directory into a .agrc bundle"
    )
    pack_parser.add_argument(
        "source",
        type=Path,
        help="Source directory to pack"
    )
    pack_parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Output .agrc file path (default: <source>.agrc)"
    )
    pack_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    # visualize command
    visualize_parser = subparsers.add_parser(
        "visualize",
        help="Start visualization studio for agent editing and debugging"
    )
    visualize_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )
    visualize_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the visualization server (default: 127.0.0.1)"
    )
    visualize_parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8765,
        help="Port for the visualization server"
    )
    visualize_parser.add_argument(
        "--mode",
        "-m",
        choices=["sync", "async", "parallel"],
        default="async",
        help="Execution mode"
    )
    visualize_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    # shell command
    shell_parser = subparsers.add_parser(
        "shell",
        help="Interactive shell for agent execution"
    )
    shell_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )
    shell_parser.add_argument(
        "--mode",
        "-m",
        choices=["sync", "async", "parallel"],
        default="async",
        help="Execution mode"
    )
    shell_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    shell_parser.add_argument(
        "--log",
        "-l",
        action="store_true",
        help="Show execution logs"
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point.

    Args:
        argv: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "run":
        return command_run(
            file=args.file,
            input_json=args.input,
            mode=args.mode,
            verbose=args.verbose
        )
    elif args.command == "validate":
        return command_validate(file=args.file)
    elif args.command == "info":
        return command_info(file=args.file)
    elif args.command == "pack":
        output = args.output or Path(str(args.source) + ".agrc")
        pack_bundle(args.source, output, args.verbose)
        return 0
    elif args.command == "shell":
        return command_shell(
            file=args.file,
            mode=args.mode,
            verbose=args.verbose,
            show_logs=args.log
        )
    elif args.command == "visualize":
        return command_visualize(
            file=args.file,
            host=args.host,
            port=args.port,
            mode=args.mode,
            verbose=args.verbose
        )
    elif args.command == "serve":
        return command_serve(
            file=args.file,
            mode=args.mode,
            verbose=args.verbose
        )
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
