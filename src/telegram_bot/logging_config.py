"""Logging configuration module for Telegram Bot service.

Provides robust logging setup with colored console banner and configuration summary.

Features:
    - Colored startup banner
    - Configuration summary display
    - Multi-worker safe (prints banner only once)
    - Configurable log levels
    - File logging with rotation
    - Separate error log file
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from telegram_bot.config.settings import Settings

# Flag file to track if banner was already printed (for multi-worker scenarios)
_BANNER_FLAG_FILE = "/tmp/.telegram_bot_banner_printed"
_BANNER_FLAG_PATH = Path(_BANNER_FLAG_FILE)

# Module-level flag to track if this process printed the banner
_banner_printed_by_this_process = False

# Global log directory
_LOG_DIR: Path = Path("./logs")

# Log formats
_LOG_FORMAT_DETAILED = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
)
_LOG_FORMAT_SIMPLE = "%(asctime)s | %(levelname)-8s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============================================================================
# ANSI Color Codes
# ============================================================================
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "white": "\033[97m",
    "red": "\033[31m",
    # Bright variants for better visibility
    "b_blue": "\033[94m",
    "b_cyan": "\033[96m",
    "b_green": "\033[92m",
    "b_yellow": "\033[93m",
    "b_magenta": "\033[95m",
}

# Color shortcuts for banner
_B = COLORS["bold"]
_R = COLORS["reset"]
_BC = COLORS["b_cyan"]
_BG = COLORS["b_green"]
_BY = COLORS["b_yellow"]
_BM = COLORS["b_magenta"]
_BB = COLORS["b_blue"]

# fmt: off
BANNER = f"""
{_B}{_BC} ████████╗{_BG}  ██████╗ {_BY} ██████╗ {_BM}  ██████╗ {_BB} ████████╗{_R}
{_BC} ╚══██╔══╝{_BG} ██╔════╝ {_BY} ██╔══██╗{_BM} ██╔═══██╗{_BB} ╚══██╔══╝{_R}
{_BC}    ██║   {_BG} ██║  ███╗{_BY} ██████╔╝{_BM} ██║   ██║{_BB}    ██║   {_R}
{_BC}    ██║   {_BG} ██║   ██║{_BY} ██╔══██╗{_BM} ██║   ██║{_BB}    ██║   {_R}
{_BC}    ██║   {_BG} ╚██████╔╝{_BY} ██████╔╝{_BM} ╚██████╔╝{_BB}    ██║   {_R}
{_BC}    ╚═╝   {_BG}  ╚═════╝ {_BY} ╚═════╝ {_BM}  ╚═════╝ {_BB}    ╚═╝   {_R}
{_R}"""  # noqa: E501
# fmt: on


def _try_acquire_banner_lock() -> bool:
    """Try to acquire banner lock atomically using exclusive file creation.

    Returns:
        True if this process should print the banner, False otherwise.
    """
    try:
        # O_CREAT | O_EXCL ensures atomic creation - fails if file exists
        fd = os.open(_BANNER_FLAG_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except OSError:
        return False


def _cleanup_banner_flag() -> None:
    """Remove banner flag file for fresh container starts."""
    try:
        if _BANNER_FLAG_PATH.exists():
            _BANNER_FLAG_PATH.unlink()
    except OSError:
        pass


def _mask_secret(secret: str) -> str:
    """Mask secret for display, showing only first and last char.

    Args:
        secret: Secret string to mask.

    Returns:
        Masked secret string.
    """
    if not secret:
        return "(not set)"
    if len(secret) <= 4:
        return "****"
    return f"{secret[:2]}{'*' * (len(secret) - 4)}{secret[-2:]}"


def print_banner() -> None:
    """Print the service startup banner."""
    global _banner_printed_by_this_process  # noqa: PLW0603
    if not _try_acquire_banner_lock():
        return

    _banner_printed_by_this_process = True
    print(BANNER)
    print(f"{COLORS['dim']}{'─' * 72}{COLORS['reset']}")
    print(
        f"{COLORS['cyan']}{COLORS['bold']}  "
        f"Telegram Bot Webhook Service{COLORS['reset']}"
    )
    print(f"{COLORS['dim']}{'─' * 72}{COLORS['reset']}\n")


def print_config_summary(settings: "Settings") -> None:
    """Print a formatted configuration summary organized by categories.

    Args:
        settings: Settings instance with loaded configuration.
    """
    if not _banner_printed_by_this_process:
        return  # Banner wasn't printed by this process

    c = COLORS

    def _line(label: str, value: str, color: str = "cyan") -> None:
        print(f"  {c['dim']}│{c['reset']} {label:<28} {c[color]}{value}{c['reset']}")

    def _header(icon: str, title: str, color: str) -> None:
        print(f"\n  {c[color]}{icon} {title}{c['reset']}")
        print(f"  {c['dim']}├{'─' * 50}{c['reset']}")

    # =========================================================================
    # Webhook Configuration
    # =========================================================================
    _header("▶", "Webhook Configuration", "green")
    _line("Webhook URL", settings.webhook_url)
    _line("Webhook Path", settings.webhook_path)
    _line("Secret Token", _mask_secret(settings.webhook_secret.get_secret_value()))
    _line("Max Connections", str(settings.webhook_max_connections))
    _line(
        "IP Filter Enabled",
        str(settings.webhook_ip_filter_enabled).lower(),
        "green" if settings.webhook_ip_filter_enabled else "yellow",
    )
    _line("Drop Pending Updates", str(settings.webhook_drop_pending_updates).lower())

    # =========================================================================
    # Server Configuration
    # =========================================================================
    _header("▶", "Server Configuration", "blue")
    _line("Host", settings.server_host)
    _line("Port", str(settings.server_port))
    _line(
        "Environment",
        settings.environment,
        "green" if settings.environment == "production" else "yellow",
    )
    _line(
        "Debug Mode", str(settings.debug).lower(), "red" if settings.debug else "green"
    )

    # =========================================================================
    # Concurrency Configuration
    # =========================================================================
    _header("▶", "Concurrency Configuration", "magenta")
    _line("Workers", str(settings.workers))
    _line(
        "Limit Concurrency",
        str(settings.limit_concurrency) if settings.limit_concurrency else "unlimited",
    )
    _line(
        "Limit Max Requests",
        (
            str(settings.limit_max_requests)
            if settings.limit_max_requests
            else "unlimited"
        ),
    )
    _line("Backlog", str(settings.backlog))

    # =========================================================================
    # Timeout Configuration
    # =========================================================================
    _header("▶", "Timeout Configuration", "cyan")
    _line("Keep Alive", f"{settings.timeout_keep_alive}s")
    _line(
        "Graceful Shutdown",
        (
            f"{settings.timeout_graceful_shutdown}s"
            if settings.timeout_graceful_shutdown
            else "default"
        ),
    )

    # =========================================================================
    # Performance Configuration
    # =========================================================================
    _header("▶", "Performance Configuration", "yellow")
    _line("HTTP Implementation", settings.http_implementation)
    _line("Loop Implementation", settings.loop_implementation)

    # =========================================================================
    # Logging Configuration
    # =========================================================================
    _header("▶", "Logging Configuration", "green")
    _line("Level", settings.log_level, "green")
    _line(
        "Log to File",
        str(settings.log_to_file).lower(),
        "green" if settings.log_to_file else "yellow",
    )
    _line("Directory", settings.log_dir)
    _line("Max File Size", f"{settings.log_max_size_mb} MB")
    _line("Backup Count", str(settings.log_backup_count))

    # =========================================================================
    # Footer
    # =========================================================================
    print(f"\n{c['dim']}{'─' * 72}{c['reset']}")
    print(
        f"  {c['green']}{c['bold']}✓ Service ready{c['reset']} "
        f"{c['dim']}│{c['reset']} "
        f"Health: {c['cyan']}http://localhost:{settings.server_port}/health{c['reset']}"
    )
    print(f"{c['dim']}{'─' * 72}{c['reset']}\n")


def setup_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
    settings: "Settings | None" = None,
) -> logging.Logger:
    """Configure application logging with console and optional file handlers.

    Args:
        level: The logging level to use.
        settings: Optional Settings instance for file logging configuration.

    Returns:
        Configured logger instance.
    """
    global _LOG_DIR  # noqa: PLW0603

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels, handlers filter

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level, logging.INFO))
    console_formatter = logging.Formatter(_LOG_FORMAT_SIMPLE, datefmt=_DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File Handlers (if enabled and settings provided)
    if settings and settings.log_to_file:
        _LOG_DIR = Path(settings.log_dir)
        _LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Main log file with rotation
        log_file = _LOG_DIR / "telegram_bot.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=settings.log_max_size_mb * 1024 * 1024,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # Capture all levels to file
        file_formatter = logging.Formatter(_LOG_FORMAT_DETAILED, datefmt=_DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # Error log file (separate file for errors only)
        error_log_file = _LOG_DIR / "telegram_bot.error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=settings.log_max_size_mb
            * 1024
            * 1024
            // 2,  # Half size for errors
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)

    logger = logging.getLogger("telegram_bot")

    # Print startup banner and config summary
    print_banner()
    if settings:
        print_config_summary(settings)

    logger.info("Logging configured with level: %s", level)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: The name for the logger.

    Returns:
        Logger instance.
    """
    return logging.getLogger(f"telegram_bot.{name}")


def get_logs_directory() -> Path:
    """Get the logs directory path.

    Returns:
        Path object pointing to logs directory.
    """
    return _LOG_DIR
