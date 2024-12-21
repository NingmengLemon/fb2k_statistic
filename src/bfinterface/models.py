from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel


class VolumeType(Enum):
    DB = "db"
    LINEAR = "linear"


class PlaybackState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class _PlayerInfo(TypedDict):
    name: str
    title: str
    version: str
    pluginVersion: str


class _PlayerActiveItem(TypedDict):
    playlistId: str
    playlistIndex: int
    index: int
    position: float
    duration: float
    columns: list[str]


class _VolumeInfo(TypedDict):
    isMuted: bool
    max: float
    min: float
    type: VolumeType
    value: float


class _PlaylistInfo(TypedDict):
    id: str
    index: int
    title: str
    isCurrent: bool
    itemCount: int
    totalTime: float


class PlayerState(TypedDict):
    activeItem: _PlayerActiveItem
    info: _PlayerInfo
    playbackMode: int
    playbackModes: list[str]
    playbackState: PlaybackState
    volume: _VolumeInfo
    options: list[dict[str, Any]]


class _PlaylistItemInfo(TypedDict):
    columns: list[str]


class PlaylistItemsResult(TypedDict):
    offset: int
    totalCount: int
    items: list[_PlaylistItemInfo]


class QueryResponse(BaseModel):
    player: PlayerState | None = None
    playlists: list[_PlaylistInfo] | None = None
    playlistItems: PlaylistItemsResult | None = None


class QueryBody(TypedDict):
    player: bool
    trcolumns: str
    playlists: bool
    playlistItems: bool
    plref: str
    plrange: str
    plcolumns: str
