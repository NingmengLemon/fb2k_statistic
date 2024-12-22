import asyncio
import atexit
import logging
import os
import sys
import pathlib

from src.statistic_collector import StatisticCollector, StatisticConfig

LOCK_FILE = pathlib.Path(os.path.expanduser("~")).joinpath("fb2kstat.lock")


async def main():
    if LOCK_FILE.exists():
        print("Already running")
        print(f"If actually not running, remove `{LOCK_FILE!s}` and try again")
        sys.exit(0)
    LOCK_FILE.touch()
    atexit.register(lambda: os.remove(LOCK_FILE))
    if "--debug" in sys.argv:
        logging.basicConfig(
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=logging.DEBUG,
        )

    config_file = "config.json"
    if not os.path.exists(config_file):
        default = StatisticConfig()
        with open(config_file, "w+", encoding="utf-8") as fp:
            fp.write(default.model_dump_json(indent=4))
        print("Edit config.json and launch app again")
        sys.exit(0)

    with open(config_file, "r", encoding="utf-8") as fp:
        config = StatisticConfig.model_validate_json(fp.read())

    collector = StatisticCollector(config)
    await collector.collect_forever()


asyncio.run(main())
