"""CLI entrypoint for the gather module."""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import click

from gather.config import GatherConfig
from gather.connectors import CONNECTOR_REGISTRY
from gather.connectors.base import BaseConnector, RawTicket
from gather.consolidator import consolidate
from gather.models import GatheredData, GatherMetadata

logger = logging.getLogger(__name__)

# Resolve ${ENV_VAR} references in auth values
_ENV_RE = re.compile(r"\$\{(\w+)\}")


def _setup_logging() -> Path:
    """Configure logging to a timestamped file in logs/."""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"gather_{ts}.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )
    # Quiet down httpx/httpcore at INFO level
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return log_file


def _resolve_env(value: str) -> str:
    """Replace ${VAR} placeholders with environment variable values."""

    def _replace(match: re.Match) -> str:
        var = match.group(1)
        val = os.environ.get(var)
        if val is None:
            raise click.ClickException(f"Environment variable {var} is not set")
        return val

    return _ENV_RE.sub(_replace, value)


def _resolve_auth(auth: dict[str, str]) -> dict[str, str]:
    return {k: _resolve_env(v) if isinstance(v, str) else v for k, v in auth.items()}


async def run_gather(output: Path, config: GatherConfig) -> None:
    connectors: list[BaseConnector] = []

    for name, source in config.sources.items():
        cls = CONNECTOR_REGISTRY.get(source.type)
        if cls is None:
            logger.warning("Unknown source type '%s' for '%s', skipping", source.type, name)
            continue

        # Resolve env var references in auth
        resolved = source.model_copy(update={"auth": _resolve_auth(source.auth)})
        connectors.append(cls(name, resolved))
        logger.info("Configured source '%s' (type=%s)", name, source.type)

    if not connectors:
        logger.error("No connectors configured. Check your sources.yaml")
        return

    logger.info(
        "Gathering from %d source(s): %s",
        len(connectors),
        ", ".join(c.name for c in connectors),
    )

    # Fetch from all sources concurrently
    all_raw: list[RawTicket] = []
    results = await asyncio.gather(
        *(c.fetch_tickets() for c in connectors)
    )
    for tickets in results:
        all_raw.extend(tickets)

    logger.info("Fetched %d raw tickets", len(all_raw))

    # Consolidate
    consolidated = consolidate(all_raw)
    logger.info(
        "Consolidated into %d tickets (from %d raw)",
        len(consolidated),
        len(all_raw),
    )

    # Write output
    data = GatheredData(
        tickets=consolidated,
        metadata=GatherMetadata(
            sources=[c.name for c in connectors],
        ),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(data.model_dump(mode="json"), indent=2, default=str)
    )
    logger.info("Written %d tickets to %s", len(consolidated), output)


@click.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default="sources.yaml",
    help="Path to YAML config file",
)
def main(config_path: Path) -> None:
    """Gather support tickets from configured services."""
    log_file = _setup_logging()
    logger.info("Log file: %s", log_file)
    logger.info("Loading config from %s", config_path)

    config = GatherConfig.from_yaml(config_path)
    # Resolve output path relative to the config file, not CWD
    output = Path(config.output)
    if not output.is_absolute():
        output = config_path.resolve().parent / output

    asyncio.run(run_gather(output, config))
