import asyncio
from dataclasses import dataclass
import json
import logging
import time

import aiohttp
from sqlmodel import create_engine, SQLModel, Session, select

from .beefweb import BeefwebClient
from .beefweb.models import PlaybackState, PlayerStateInfo
from .models import StatisticConfig, MusicItem, PlaybackRecord
from .utils import calc_music_id, handle_artist_field, lock

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


@dataclass(frozen=True)
class PlayerState:
    playback_state: PlaybackState
    position: float
    duration: float
    music_id: str | None
    metadata: dict[str, str] | None
    time: float
    volume_percent: float


class StatisticCollector:
    def __init__(self, config: StatisticConfig):
        self._config = config.model_copy(deep=True)
        logger.debug("config = %s", self._config.model_dump_json())
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

        self._last_state: PlayerState | None = None
        # 用于当前曲目的状态缓冲，切歌/停止/断连时整理写入到数据库并清空
        self._buffer: list[PlayerState] = []

    def _flush_buffer(self):
        """写入数据库清空缓冲区的函数"""
        self._buffer = [s for s in self._buffer if s.playback_state != "stopped"]
        if not self._buffer:
            return
        last_state = self._buffer[0]
        init_time = last_state.time
        now_time = time.time()

        duration = 0
        for i, state in enumerate(self._buffer):
            if i == 0:
                continue
            if (state.time - last_state.time + self._config.max_tolerant_delay) > (
                d := (state.position - last_state.position)
            ) > 0 and last_state.playback_state == "playing":
                duration += d
            last_state = state

        if (
            (now_time - last_state.time + self._config.max_tolerant_delay)
            > (d := (last_state.duration - last_state.position))
            > 0
        ):
            duration += d
        self._add_music(
            last_state.music_id, last_state.metadata, duration=last_state.duration
        )
        if (
            now_time - init_time + self._config.max_tolerant_delay >= duration
            and duration / last_state.duration >= self._config.record_threshold
        ):
            self._add_record(last_state.music_id, init_time, duration)
        self._buffer.clear()
        logger.info("buffer flushed")

    def _add_record(self, music_id: str, start_time: float, duration: float):
        with self._dbsess as sess:
            sess.add(
                PlaybackRecord(
                    music_id=music_id,
                    time=start_time,
                    duration=duration,
                )
            )
            sess.commit()
            logger.debug(
                "add new record, duration=%.3f, music_id=%s", duration, music_id
            )

    def _add_music(self, music_id: str, metadata: dict[str, str], duration: float):
        with self._dbsess as sess:
            item = sess.exec(
                select(MusicItem).where(MusicItem.id == music_id)
            ).one_or_none()
            if item is None:
                sess.add(
                    MusicItem(
                        id=music_id,
                        title=metadata["%title%"],
                        artists=metadata.get("%artist%", ""),
                        album=metadata.get("%album%"),
                        duration=duration,
                    )
                )
                sess.commit()
                logger.debug("add new music, metadata=%s", metadata)

    @property
    def _dbsess(self):
        return Session(self._engine)

    # pylint: disable=W1202, W1203
    def _compare(self, old: PlayerState | None, new: PlayerState | None):
        # None 表示断连状态
        # 总之往缓冲区里狠狠鸿儒(bs)
        match (old, new):
            case (None, None):
                return
            case (None, _):
                logger.info("connected")
                self._buffer.append(new)
                return
            case (_, None):
                logger.info("disconnected")
                self._flush_buffer()
                return
            case (x, y) if x.metadata is None and y.metadata is None:
                return
            case (_, y) if y.metadata is None:
                logger.info("stop")
                self._flush_buffer()
                return
            case (x, _) if x.metadata is None:
                logger.info(f"start {new.metadata["%title%"]!r}")
                self._buffer.append(new)
                return

        if old.music_id == new.music_id:
            match (old.playback_state, new.playback_state):
                case ("paused", "playing"):
                    logger.info("resume")
                case ("playing", "paused"):
                    logger.info("pause")
                case ("playing", "playing"):
                    if old.volume_percent == new.volume_percent:
                        logger.info(
                            f"position {old.position:.4f} -> {new.position:.4f}"
                        )
                    else:
                        logger.info(
                            f"volume {old.volume_percent:.2f}% -> {new.volume_percent:.2f}%"
                        )
        else:
            logger.info(
                f"switch {old.metadata["%title%"]!r} -> {new.metadata["%title%"]!r}"
            )
            self._flush_buffer()
        self._buffer.append(new)

    def _switch_state(self, new_state: PlayerState | None):
        """传入None时表示连接断开"""
        self._compare(self._last_state, new_state)
        logger.debug("current buffer: %s", self._buffer)
        self._last_state = new_state

    def _player_to_state(self, player: PlayerStateInfo):
        """
        将实质是 dict 的 PlayerStateInfo 简化为实质是 dataclass 的 PlayerState

        同时进行一些必要的标准化处理
        """
        columns = player["activeItem"]["columns"]
        if len(columns) == len(self._query_columns):
            metadata = {
                k: v for k, v in zip(self._query_columns, columns) if v != _VOID_FIELD
            }
            raw_artists = metadata.get("%artist%", None)
            if raw_artists:
                artists = handle_artist_field(
                    raw_artists,
                    self._config.fb2k_artist_delimiters,
                    self._config.preserved_artists,
                )
            else:
                artists = []
            metadata["%artist%"] = self._config.database_artist_delimiter.join(artists)
            music_id = calc_music_id(metadata, *self._query_columns)
            logger.debug("extract metadata: %s", metadata)
        else:
            # 长度不匹配说明现在是停止状态，没有元数据
            metadata = music_id = None
            logger.debug("stopped state, no metadata")

        volume = player["volume"]
        return PlayerState(
            playback_state=player["playbackState"],
            position=player["activeItem"]["position"],
            duration=player["activeItem"]["duration"],
            metadata=metadata,
            time=time.time(),
            volume_percent=(
                0.0
                if volume["isMuted"]
                else (
                    (volume["value"] - volume["min"])
                    / (volume["max"] - volume["min"])
                    * 100
                )
            ),
            music_id=music_id,
        )

    @lock()
    async def collect_forever(self):
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
                except aiohttp.ClientConnectionError as e:
                    logger.warning("exception when collecting: %s", e)
                self._switch_state(None)
                logger.info(f"retry after {self._config.retry_interval}s")
                await asyncio.sleep(self._config.retry_interval)
        finally:
            await self.close()
            self._flush_buffer()
            logger.info("stop collecting")

    async def close(self):
        await self._client.close()
