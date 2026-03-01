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

Logging level env var: PMR_LOG_LEVEL  (DEBUG, INFO, WARNING, ERROR)
"""

import argparse
import logging
import logging.handlers
import os
import sys
import tomllib  # Python 3.11+; use `pip install tomli` and `import tomli as tomllib` for older versions
from pathlib import Path
from typing import Any
from pmr_cache import PMRCache, InstanceMismatchError, CacheNotInitialisedError
from workspaces import cache_workspace_information
from workspace_list_to_mx_fmt import export_to_omicsdi


# ==============================================================================
# Module-level logger
# (each module in your project should do this — they all feed into the
#  root "pmr" logger that gets configured once in main())
# ==============================================================================

log = logging.getLogger("pmr.utils")


# ==============================================================================
# Global Defaults
# ==============================================================================

GLOBAL_DEFAULTS = {
    "pmr_instance": "https://models.physiomeproject.org/",
    "cache_dir": "./pmr-cache",
    "log_level": "INFO",       # DEBUG | INFO | WARNING | ERROR
    "log_file": None,          # None → terminal only
    "log_max_bytes": 10 * 1024 * 1024,  # 10 MB before rotation
    "log_backup_count": 3,              # keep 3 rotated files
}


# ==============================================================================
# Logging Setup
# ==============================================================================

# Two formatters: a compact one for the terminal, a detailed one for log files.
_TERMINAL_FORMAT = "%(levelname)-8s %(message)s"
_FILE_FORMAT     = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
_DATE_FORMAT     = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str, log_file: str | None, *, log_max_bytes: int, log_backup_count: int) -> None:
    """
    Configure the root 'pmr' logger.

    Parameters
    ----------
    level : str
        Log level name: DEBUG, INFO, WARNING, or ERROR.
    log_file : str | None
        Path to a log file. If None, output goes to stderr only.
        Uses a RotatingFileHandler so logs don't grow unboundedly.
    log_max_bytes : int
        Maximum size of a single log file before it rotates.
    log_backup_count : int
        Number of rotated backup files to keep.
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        # Can't use log.error here — logging isn't configured yet
        print(f"Warning: unknown log level '{level}', falling back to INFO.", file=sys.stderr)
        numeric_level = logging.INFO

    # Root logger for all 'pmr.*' loggers in this project
    root = logging.getLogger("pmr")
    root.setLevel(numeric_level)
    root.handlers.clear()  # Avoid duplicate handlers if called more than once

    # --- Terminal handler (always present) ---
    terminal = logging.StreamHandler(sys.stderr)
    terminal.setLevel(numeric_level)
    terminal.setFormatter(logging.Formatter(_TERMINAL_FORMAT))
    root.addHandler(terminal)

    # --- File handler (optional) ---
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(file_handler)
        # This log line will appear in the file but also on the terminal
        logging.getLogger("pmr").info("Logging to file: %s", log_path.resolve())


# ==============================================================================
# Config File Loading
# ==============================================================================

def load_config_file(path: str) -> dict[str, Any]:
    """
    Load a TOML config file. Expected structure:

        [global]
        pmr_instance    = "https://my-pmr-instance.example.com"
        cache_dir = "/data/pmr-cache"
        log_level        = "DEBUG"          # DEBUG | INFO | WARNING | ERROR
        log_file         = "/var/log/pmr-utils.log"   # omit for terminal-only
        log_max_bytes    = 10485760         # 10 MB (optional)
        log_backup_count = 3               # (optional)

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
        "log_level": (
            cli_args.log_level                          # --log-level DEBUG
            or file_global.get("log_level")
            or os.environ.get("PMR_LOG_LEVEL")
            or GLOBAL_DEFAULTS["log_level"]
        ),
        "log_file": (
            cli_args.log_file                           # --log-file /path/to/file.log
            or file_global.get("log_file")
            or os.environ.get("PMR_LOG_FILE")
            or GLOBAL_DEFAULTS["log_file"]
        ),
        "log_max_bytes": (
            file_global.get("log_max_bytes") or GLOBAL_DEFAULTS["log_max_bytes"]
        ),
        "log_backup_count": (
            file_global.get("log_backup_count") or GLOBAL_DEFAULTS["log_backup_count"]
        ),
    }
    return resolved


# ==============================================================================
# Command Implementations
# ==============================================================================

def cmd_cache_workspace_information(args: argparse.Namespace, config: dict[str, Any]) -> int:
    """Populate the workspace cache information."""

    try:
        cache = PMRCache(config["cache_dir"], config["pmr_instance"])
    except InstanceMismatchError as e:
        print(f"Error: instance mismatch - {e}")
        return 1
    except CacheNotInitialisedError as e:
        print(f"Error: cache not initialised - {e}")
        return 1
    
    return cache_workspace_information(cache, regex=args.regex, workspace=args.workspace, all=args.all, 
                                       force_refresh=args.force_refresh)


def cmd_omicsdi_export(args: argparse.Namespace, config: dict[str, Any]) -> int:
    """Export OmicsDI metadata for cached workspaces."""

    try:
        cache = PMRCache(config["cache_dir"], config["pmr_instance"])
    except InstanceMismatchError as e:
        print(f"Error: instance mismatch - {e}")
        return 1
    except CacheNotInitialisedError as e:
        print(f"Error: cache not initialised - {e}")
        return 1
    
    mx_xml = export_to_omicsdi(cache)
    if args.output:
        with open(args.output, 'w', encoding="utf-8") as f:
            f.write(mx_xml)
    else:
        print(mx_xml)

    return 0


def cmd_greet(args: argparse.Namespace, config: dict[str, Any]) -> int:
    """Say hello to someone, optionally loudly."""
    log.debug("cmd_greet called with args: %s", args)
    log.info("Using PMR instance: %s", config["pmr_instance"])
    log.info("Output directory:   %s", config["cache_dir"])

    greeting = f"Hello, {args.name}!"
    if args.shout:
        log.debug("--shout flag set, converting to uppercase")
        greeting = greeting.upper()
    if args.repeat > 1:
        log.debug("Repeating greeting %d times", args.repeat)
        greeting = " ".join([greeting] * args.repeat)
    print(greeting)
    return 0


def cmd_process(args: argparse.Namespace, config: dict[str, Any]) -> int:
    """Process a file with optional transformation."""
    log.debug("cmd_process called with args: %s", args)
    log.info("Processing file: %s", args.input)
    log.info("Output: %s", args.output or config["output_dir"])
    log.info("Mode: %s", args.mode)
    if args.dry_run:
        log.warning("[DRY RUN] No changes written.")
    return 0


def cmd_status(args: argparse.Namespace, config: dict[str, Any]) -> int:
    """Check the status of something."""
    log.debug("cmd_status called with args: %s", args)
    log.info("[PMR]        %s", config['pmr_instance'])
    log.info("[Cache dir] %s", config['cache_dir'])
    targets = args.targets or ["all"]
    log.info("Checking status of: %s", ', '.join(targets))
    if args.verbose:
        log.info("  [verbose] Extra detail would appear here.")
    
    for target in targets:
        # Simulated status check
        log.debug("Querying target: %s", target)
        log.info("  %s → OK", target)
    
    return 0


# ==============================================================================
# Subcommand Argument Definitions
# ==============================================================================
def _args_cache_workspace_information(p: argparse.ArgumentParser):
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--regex",
        help='Specify a regex to determine matching workspaces to cache information for'
    )
    group.add_argument(
        "--workspace",
        help='Specify a single workspace to cache information for, rather than searching PMR'
    )
    group.add_argument(
        "--all", 
        action='store_true', 
        default=False,
        help='Cache information for all available (public) workspaces in PMR'
    )
    p.add_argument(
        "--force-refresh",
        action='store_true',
        default=False,
        help='Force refresh of cached information even if it already exists'
    )


def _args_omicsdi_export(p: argparse.ArgumentParser):
    p.add_argument(
        "--output",
        metavar="FILE",
        help="Path to output XML file (default: print to terminal)"
    )


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
    "cache-workspace": {
        "func": cmd_cache_workspace_information,
        "help": "Cache workspace information",
        "description": "Cache information for one or more workspaces.",
        "add_args": _args_cache_workspace_information,
    },
    "omicsdi-export": {
        "func": cmd_omicsdi_export,
        "help": "Export OmicsDI metadata",
        "description": "Export metadata for cached workspaces in OmicsDI format.",
        "add_args": _args_omicsdi_export,
    },
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

    # --- Logging options ---
    log_group = parser.add_argument_group(
        "logging options",
        "Control log verbosity and destination. Can also be set via a config file or env vars.",
    )
    log_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        metavar="LEVEL",
        help=(
            "Log verbosity: DEBUG (most verbose) → INFO → WARNING → ERROR (least verbose). "
            f"(env: PMR_LOG_LEVEL, default: {GLOBAL_DEFAULTS['log_level']})"
        ),
    )
    log_group.add_argument(
        "--log-file", metavar="FILE",
        help=(
            "Write logs to this file in addition to the terminal. "
            "The file rotates automatically when it reaches 10 MB. "
            "(env: PMR_LOG_FILE, default: terminal only)"
        ),
    )
    log_group.add_argument(
        "--debug",
        action="store_true",
        help="Shorthand for --log-level DEBUG",
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

    # --debug is a convenient shorthand for --log-level DEBUG
    if args.debug:
        config["log_level"] = "DEBUG"

    # Configure logging as early as possible so all subsequent code can use it
    setup_logging(
        level=config["log_level"],
        log_file=config["log_file"],
        log_max_bytes=config["log_max_bytes"],
        log_backup_count=config["log_backup_count"],
    )

    log.debug("Resolved config: %s", config)
    log.debug("Parsed args: %s", args)

    return COMMANDS[args.command]["func"](args, config)


if __name__ == "__main__":
    sys.exit(main())