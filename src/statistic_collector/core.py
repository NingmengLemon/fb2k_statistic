import copy
from dataclasses import dataclass
import json
import logging
import time

from sqlmodel import create_engine, SQLModel

from .beefweb import BeefwebClient
from .beefweb.models import (
    PlaybackState,
    PlayerActiveItemInfo,
    PlayerStateInfo,
    QueryResponse,
    GetPlayerResponse,
)
from .models import StatisticConfig, MusicItem, PlaybackRecord
from .utils import calc_music_id, handle_artist_field

_TABLES_TO_CREATE = [
    SQLModel.metadata.tables[t.__tablename__] for t in (MusicItem, PlaybackRecord)
]
_REQUIRED_FIELDS = [
    r"%title%",
    r"%artist%",
    r"%album%",
    r"%length_seconds_fp%",
]
_VOID_FIELD = "?"
logger = logging.getLogger(__name__)


@dataclass
class PlayerState:
    playback_state: PlaybackState
    position: float
    duration: float
    metadata: dict[str, str] | None
    time: float


class StatisticCollector:
    def __init__(self, config: StatisticConfig):
        self._config = config.model_copy(deep=True)
        self._client = BeefwebClient(
            root=self._config.api_root,
            username=self._config.username,
            password=self._config.password,
        )

        dburl = self._config.database_url
        self._engine = create_engine(dburl)
        SQLModel.metadata.create_all(bind=self._engine, tables=_TABLES_TO_CREATE)

        self._columns_as_id = [c.lower().strip() for c in self._config.columns_as_id]
        self._query_columns = self._columns_as_id.copy()
        for field in _REQUIRED_FIELDS:
            if field not in self._query_columns:
                self._query_columns.append(field)

        self._is_collecting = False
        self._last_state: PlayerState | None = None

    # pylint: disable=W1203
    def _compare_and_record(self, old: PlayerState | None, new: PlayerState | None):
        # TODO: 变更状态时的数据库操作
        # 先不对数据库做操作，打印试试看
        match (old, new):
            case (None, _):
                logger.info("connect")
                return
            case (_, None):
                logger.info("disconnect")
                return

        old_id = calc_music_id(old.metadata, *self._columns_as_id)
        new_id = calc_music_id(new.metadata, *self._columns_as_id)
        if old_id == new_id:
            match (old.playback_state, new.playback_state):
                case ("paused", "playing"):
                    logger.info("resume")
                case ("playing", "paused"):
                    logger.info("pause")
                case ("playing", "playing"):
                    logger.info(f"position {old.position} -> {new.position}")
        else:
            logger.info(
                f"switch {old.metadata["%title%"]} -> {new.metadata["%title%"]}"
            )

    def _switch_state(self, new_state: PlayerState | None):
        """传入None时表示连接断开"""
        self._compare_and_record(self._last_state, new_state)
        self._last_state = copy.deepcopy(new_state)

    def _player_to_state(self, player: PlayerStateInfo):
        columns = player["activeItem"]["columns"]
        if len(columns) == len(self._query_columns):
            metadata = {k: v for k, v in zip(self._query_columns, columns)}
        else:
            metadata = None

        raw_artists = metadata.get("%artist%", "")
        if raw_artists == "?":
            artists = []
        else:
            artists = handle_artist_field(
                raw_artists,
                self._config.fb2k_artist_delimiters,
                self._config.preserved_artists,
            )
        logger.debug("extract artists: %s", artists)
        metadata["%artist%"] = self._config.database_artist_delimiter.join(artists)

        return PlayerState(
            playback_state=player["playbackState"],
            position=player["activeItem"]["position"],
            duration=player["activeItem"]["duration"],
            metadata=metadata,
            time=time.time(),
        )

    async def collect_forever(self):
        self._is_collecting = True
        try:
            while True:
                try:
                    async for response in self._client.query_updates(
                        player=True,
                        trcolumns=",".join(self._query_columns),
                    ):
                        player = response.player
                        if player is None:
                            continue
                        logger.debug(
                            "receive sse: %s", json.dumps(player, ensure_ascii=False)
                        )
                        self._switch_state(self._player_to_state(player))
                except Exception as e:
                    # TODO: 对连接错误做特殊处理，超时什么的
                    logger.warning("Exception when collecting: %s", e)
                    self._switch_state(None)
        finally:
            await self.close()

    async def close(self):
        await self._client.close()
