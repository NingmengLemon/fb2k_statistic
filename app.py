import asyncio
import logging
import os
import sys

from filelock import FileLock, Timeout

from src.statistic_collector import StatisticCollector, StatisticConfig

logger = logging.getLogger(__name__)


async def main():
    logging_config = {
        "format": "%(asctime)s - %(levelname)s - %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
        "level": logging.DEBUG if "--debug" in sys.argv else logging.INFO,
    }
    if "--logfile" in sys.argv:
        logging_config["filename"] = "fb2kstat.log"
        logging_config["filemode"] = "w+"
        logging_config["encoding"] = "utf-8"
    logging.basicConfig(**logging_config)

    config_file = "config.json"
    if not os.path.exists(config_file):
        default = StatisticConfig()
        with open(config_file, "w+", encoding="utf-8") as fp:
            fp.write(default.model_dump_json(indent=4))
        print("Edit config.json and relaunch app")
        sys.exit(0)

    with open(config_file, "r", encoding="utf-8") as fp:
        config = StatisticConfig.model_validate_json(fp.read())
    dblockfile = config.database_url.removeprefix("sqlite:///") + ".lock"
    dblock = FileLock(dblockfile, timeout=0)
    try:
        with dblock:
            collector = StatisticCollector(config)
            await collector.collect_forever()
    except Timeout:
        logger.critical("database busy")


asyncio.run(main())
