import posixpath
import uuid
from pydantic import BaseModel
from pydantic import Field as PydField
from sqlmodel import SQLModel, Field, Relationship


class StatisticConfig(BaseModel):
    # beefweb 的 API 端点
    api_root: str = "http://127.0.0.1:8880/api"
    # 连接到 beefweb 的凭据
    username: str | None = None
    password: str | None = None
    # 数据库位置
    database_url: str = PydField(
        "sqlite:///"
        + posixpath.join(posixpath.expanduser("~"), "fb2k_playback_statistic.db")
    )
    # 用作计算音乐文件哈希的字段们，顺序敏感
    columns_as_id: list[str] = [r"%title%", r"%artist%"]  # , r"%album%"]
    # 将这些艺术家视为整体，保证不被分割符切割
    preserved_artists: list[str] = ["Leo/need"]
    # 允许的元数据中的分割符
    # 这俩默认的分别来自 wyy 和 fb2k
    fb2k_artist_delimiters: list[str] = ["/", ","]
    # 数据库中的艺术家分割符
    database_artist_delimiter: str = "|"
    # 当播放进度超过多少时才会记录播放
    record_threshold: float = Field(0.1, ge=0.0, le=1.0)
    # 重试间隔
    retry_interval: float = Field(2.0, ge=0.0)
    # 最大能容忍的延迟造成的误差
    # 计划用于进度防作弊
    max_tolerant_delay: float = Field(5.0, ge=0.0)


class MusicItem(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: str
    artists: str = ""
    album: str | None = None
    duration: float = ""
    records: list["PlaybackRecord"] = Relationship(back_populates="music")


class PlaybackRecord(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    music_id: str = Field(foreign_key="musicitem.id")
    music: MusicItem = Relationship(back_populates="records")

    time: float  # 开始听的时间戳
    duration: float  # 听的时长，不一定等于歌曲时长
