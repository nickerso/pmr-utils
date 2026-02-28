"""
pmr-utils: Andre's collection of PMR utilities.

Usage:
    pmr-utils.py [global options] <command> [command options]
    pmr-utils.py --config run.toml
    pmr-utils.py -h | --help
    pmr-utils.py <command> -h | --help

Global options (--pmr-instance, --cache-dir) can be set via:
  1. A config file (--config)
  2. Environment variables (PMR_INSTANCE, CACHE_DIR)
  3. Command-line flags

Priority order (highest to lowest):
  command-line flags > config file > environment variables > built-in defaults
"""

import argparse
import os
import sys
import tomllib  # Python 3.11+; use `pip install tomli` and `import tomli as tomllib` for older versions
from pathlib import Path
from typing import Any


# ==============================================================================
# Global Defaults
# ==============================================================================

GLOBAL_DEFAULTS = {
    "pmr_instance": "https://models.physiomeproject.org/",
    "cache_dir": "./pmr-cache",
}


# ==============================================================================
# Config File Loading
# ==============================================================================

def load_config_file(path: str) -> dict[str, Any]:
    """
    Load a TOML config file. Expected structure:

        [global]
        pmr_instance    = "https://my-pmr-instance.example.com"
        cache_dir = "/data/pmr-cache"

        # Optional: record a specific run for reproducibility / version control
        [run]
        command = "greet"

        [run.args]
        name   = "Alice"
        shout  = true
        repeat = 3

    The [run] section lets you commit a specific execution to your git repo
    so you can reproduce it later with: pmr-utils.py --config run.toml
    """
    config_path = Path(path)
    if not config_path.exists():
        print(f"Error: config file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def resolve_global_config(cli_args: argparse.Namespace, file_config: dict) -> dict[str, Any]:
    """
    Merge global config from all sources using priority order:
      CLI flags > config file [global] section > env vars > built-in defaults
    """
    file_global = file_config.get("global", {})

    resolved = {
        "pmr_instance": (
            cli_args.pmr_instance                        # CLI flag (highest priority)
            or file_global.get("pmr_instance")           # config file
            or os.environ.get("PMR_INSTANCE")            # environment variable
            or GLOBAL_DEFAULTS["pmr_instance"]           # built-in default
        ),
        "cache_dir": (
            cli_args.cache_dir
            or file_global.get("cache_dir")
            or os.environ.get("PMR_CACHE_DIR")
            or GLOBAL_DEFAULTS["cache_dir"]
        ),
    }
    return resolved


# ==============================================================================
# Command Implementations
# ==============================================================================

def cmd_greet(args: argparse.Namespace, config: dict[str, Any]) -> int:
    """Say hello to someone, optionally loudly."""
    print(f"[PMR]        {config['pmr_instance']}")
    print(f"[Cache dir] {config['cache_dir']}")

    greeting = f"Hello, {args.name}!"
    if args.shout:
        greeting = greeting.upper()
    if args.repeat > 1:
        greeting = " ".join([greeting] * args.repeat)
    print(greeting)
    return 0


def cmd_process(args: argparse.Namespace, config: dict[str, Any]) -> int:
    """Process a file with optional transformation."""
    print(f"[PMR]        {config['pmr_instance']}")
    print(f"[Cache dir] {config['cache_dir']}")
    print(f"Processing file: {args.input}")
    print(f"Output: {args.output or config['cache_dir']}")
    print(f"Mode: {args.mode}")
    if args.dry_run:
        print("[DRY RUN] No changes written.")
    return 0


def cmd_status(args: argparse.Namespace, config: dict[str, Any]) -> int:
    """Check the status of something."""
    print(f"[PMR]        {config['pmr_instance']}")
    print(f"[Cache dir] {config['cache_dir']}")
    targets = args.targets or ["all"]
    print(f"Checking status of: {', '.join(targets)}")
    if args.verbose:
        print("  [verbose] Extra detail would appear here.")
    return 0


# ==============================================================================
# Subcommand Argument Definitions
# ==============================================================================

def _args_greet(p: argparse.ArgumentParser):
    p.add_argument(
        "name",
        help="Name of the person to greet",
    )
    p.add_argument(
        "--shout", "-s",
        action="store_true",
        help="Print the greeting in uppercase",
    )
    p.add_argument(
        "--repeat", "-r",
        type=int,
        default=1,
        metavar="N",
        help="Repeat the greeting N times (default: 1)",
    )


def _args_process(p: argparse.ArgumentParser):
    p.add_argument(
        "input",
        help="Path to the input file",
    )
    p.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Path to the output file (default: uses --output-dir)",
    )
    p.add_argument(
        "--mode", "-m",
        choices=["fast", "safe", "verbose"],
        default="safe",
        help="Processing mode (default: safe)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without writing any output",
    )


def _args_status(p: argparse.ArgumentParser):
    p.add_argument(
        "targets",
        nargs="*",
        metavar="TARGET",
        help="One or more targets to check (default: all)",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed status information",
    )


COMMANDS = {
    "greet": {
        "func": cmd_greet,
        "help": "Greet a person by name",
        "description": "Print a greeting for the given person. Supports shouting and repetition.",
        "add_args": _args_greet,
    },
    "process": {
        "func": cmd_process,
        "help": "Process an input file",
        "description": "Read an input file and apply a transformation, writing to a file or stdout.",
        "add_args": _args_process,
    },
    "status": {
        "func": cmd_status,
        "help": "Check the status of one or more targets",
        "description": "Query the current status of the specified targets (or all targets if none given).",
        "add_args": _args_status,
    },
}


# ==============================================================================
# Argument Parser Setup
# ==============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pmr-utils",
        description="Andre's collection of PMR utilities.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Configuration priority (highest to lowest):\n"
            "  command-line flags > --config file > env vars (PMR_INSTANCE, CACHE_DIR) > defaults\n\n"
            "Run 'pmr-utils.py <command> -h' for help on a specific command.\n\n"
            "Available commands:\n"
            + "\n".join(f"  {name:<16}{cmd['help']}" for name, cmd in COMMANDS.items())
        ),
    )

    # --- Global options (apply to all commands) ---
    global_group = parser.add_argument_group(
        "global options",
        "These options apply to all commands and can also be set via a config file or env vars.",
    )
    global_group.add_argument(
        "--config", "-c",
        metavar="FILE",
        help=(
            "Path to a TOML config file. Supports [global] settings and an optional [run] "
            "section to record the command + args for reproducibility (great for git tracking)."
        ),
    )
    global_group.add_argument(
        "--pmr-instance",
        metavar="URL",
        help=f"URL of the PMR instance (env: PMR_INSTANCE, default: {GLOBAL_DEFAULTS['pmr_instance']})",
    )
    global_group.add_argument(
        "--cache-dir",
        metavar="DIR",
        help=f"Local folder for output files (env: PMR_CACHE_DIR, default: {GLOBAL_DEFAULTS['cache_dir']})",
    )

    # --- Subcommands ---
    subparsers = parser.add_subparsers(
        dest="command",
        metavar="<command>",
    )

    for name, cmd in COMMANDS.items():
        sub = subparsers.add_parser(
            name,
            help=cmd["help"],
            description=cmd["description"],
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        cmd["add_args"](sub)

    return parser


# ==============================================================================
# Config-file [run] section → synthetic argv
# ==============================================================================

def run_section_to_argv(run_section: dict) -> list[str]:
    """
    Convert the [run] section of a config file into a synthetic argv list
    that argparse can parse. Positional args are passed as bare values;
    optional args become --flag value pairs.

    Example [run.args]:
        name   = "Alice"   →  "Alice"        (positional, no flag)
        shout  = true      →  "--shout"      (boolean flag)
        repeat = 3         →  "--repeat" "3"
    """
    command = run_section.get("command")
    if not command:
        return []

    run_args = run_section.get("args", {})
    argv = [command]

    for key, value in run_args.items():
        flag = f"--{key.replace('_', '-')}"
        if key == 'args':
            # Special case: if the user has a nested [run.args.args] section, we treat it as a list of positional args.
            argv.extend([value])
        elif isinstance(value, bool):
            if value:
                argv.append(flag)
            # False → omit (store_true style)
        elif isinstance(value, list):
            # Positional nargs="*" lists: append values bare (no flag)
            argv.extend(str(v) for v in value)
        else:
            argv.extend([flag, str(value)])
    return argv


# ==============================================================================
# Entry Point
# ==============================================================================

def main() -> int:
    parser = build_parser()

    # Print top-level help if no arguments given
    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    # First pass: extract global flags (--config, --pmr-url, --output-dir)
    # without failing on unknown subcommand arguments yet.
    pre_args, remaining = parser.parse_known_args()

    # Load config file if provided
    file_config: dict[str, Any] = {}
    if pre_args.config:
        file_config = load_config_file(pre_args.config)

    # If no command was given on the CLI, look for one in the config [run] section.
    if pre_args.command is None:
        run_section = file_config.get("run", {})
        if not run_section.get("command"):
            parser.print_help()
            return 1

        # Build argv from [run] section, then re-parse the full CLI on top.
        # CLI args always win because they're appended after (argparse last-write wins).
        config_argv = run_section_to_argv(run_section)
        # Re-inject global flags that were already parsed so they survive the full parse.
        global_flags = []
        if pre_args.pmr_instance:
            global_flags += ["--pmr-instance", pre_args.pmr_instance]
        if pre_args.cache_dir:
            global_flags += ["--cache-dir", pre_args.cache_dir]

        args = parser.parse_args(global_flags + config_argv + remaining)
    else:
        args = parser.parse_args()

    # Resolve global configuration from all sources
    config = resolve_global_config(args, file_config)

    # Ensure cache directory exists
    Path(config["cache_dir"]).mkdir(parents=True, exist_ok=True)

    return COMMANDS[args.command]["func"](args, config)


if __name__ == "__main__":
    sys.exit(main())