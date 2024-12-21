import copy
import logging

from sqlmodel import create_engine, SQLModel

from .beefweb import BeefwebClient
from .beefweb.models import (
    PlayerActiveItemInfo,
    PlayerStateInfo,
    QueryResponse,
    GetPlayerResponse,
)
from .models import StatisticConfig, MusicItem, PlaybackRecord

_TABLES_TO_CREATE = [
    SQLModel.metadata.tables[t.__tablename__] for t in (MusicItem, PlaybackRecord)
]
_REQUIRED_FIELDS = [
    r"%title%",
    r"%artist%",
    r"%album%",
    r"%length_seconds_fp%",
]


class StatisticCollector:
    def __init__(self, bfwb_client: BeefwebClient, config: StatisticConfig):
        self._config = config.model_copy(deep=True)
        self._logger = logging.getLogger(str(self))
        self._client = bfwb_client

        dburl = self._config.database_url
        self._engine = create_engine(dburl)
        SQLModel.metadata.create_all(bind=self._engine, tables=_TABLES_TO_CREATE)

        self._columns_as_id = [c.lower().strip() for c in self._config.columns_as_id]
        self._query_columns = self._columns_as_id.copy()
        for field in _REQUIRED_FIELDS:
            if field not in self._query_columns:
                self._query_columns.append(field)

        self._last_state: PlayerStateInfo | None = None

    def _switch_state(self, new_state: PlayerStateInfo | None):
        """传入None时表示结束"""
        if new_state is None:
            # TODO: 结束时要做的事
            return
        if self._last_state is None:
            self._last_state = copy.deepcopy(new_state)
            return
        # TODO: 变更状态时的数据库操作
        self._last_state = copy.deepcopy(new_state)

    async def serve_forever(self):
        while True:
            try:
                async for response in self._client.query_updates(
                    player=True,
                    trcolumns=",".join(self._query_columns),
                ):
                    player = response.player
                    if player is None:
                        continue
                    self._switch_state(player)
            except Exception as e:
                pass
