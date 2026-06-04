"""CLI entrypoint: `python main.py <url> [quality]`.

Backed by core.download_manager — same code path that the FastAPI backend uses.
"""
import os
import sys

from config import ConfigReader
from core.download_manager import build_options, run_download
from utils.logging import get_logger

logger = get_logger("cli")


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <url> [quality]")
        sys.exit(1)

    url = sys.argv[1]
    quality_override = sys.argv[2] if len(sys.argv) > 2 else None

    script_dir = os.path.dirname(os.path.abspath(__file__))
    config = ConfigReader(os.path.join(script_dir, "config.json"))
    output_path = config.get("output_path")
    options = build_options(
        url=url,
        browser=config.get("browser"),
        timeout=config.get("timeout"),
        quality_override=quality_override,
    )

    logger.info("Source detected, starting download → %s", url)
    result = run_download(options, output_path=output_path)
    if result:
        logger.info("✓ Done: %s", result)
    else:
        logger.error("✗ Download failed")
        sys.exit(2)


if __name__ == "__main__":
    main()
