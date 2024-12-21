from typing import Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel


VolumeType = Literal["db", "linear"]
PlaybackState = Literal["stopped", "playing", "paused"]


class PlayerInfo(TypedDict):
    name: str
    title: str
    version: str
    pluginVersion: str


class PlayerActiveItemInfo(TypedDict):
    playlistId: str
    playlistIndex: int
    index: int
    position: float
    duration: float
    columns: list[str]


class VolumeInfo(TypedDict):
    isMuted: bool
    max: float
    min: float
    type: VolumeType
    value: float


class PlaylistInfo(TypedDict):
    id: str
    index: int
    title: str
    isCurrent: bool
    itemCount: int
    totalTime: float


class PlayerStateInfo(TypedDict):
    activeItem: PlayerActiveItemInfo
    info: PlayerInfo
    playbackMode: int
    playbackModes: list[str]
    playbackState: PlaybackState
    volume: VolumeInfo
    options: list[dict[str, Any]]


class PlaylistItemInfo(TypedDict):
    columns: list[str]


class PlaylistItemsInfo(TypedDict):
    offset: int
    totalCount: int
    items: list[PlaylistItemInfo]


class GetPlayerResponse(BaseModel):
    player: PlayerStateInfo


class QueryResponse(BaseModel):
    player: PlayerStateInfo | None = None
    playlists: list[PlaylistInfo] | None = None
    playlistItems: PlaylistItemsInfo | None = None


class QueryParams(TypedDict):
    player: NotRequired[bool]
    trcolumns: NotRequired[str]
    playlists: NotRequired[bool]
    playlistItems: NotRequired[bool]
    plref: NotRequired[str]
    plrange: NotRequired[str]
    plcolumns: NotRequired[str]


class GetPlaylistsResponse(BaseModel):
    playlists: list[PlaylistInfo]


class GetPlaylistItemsResponse(BaseModel):
    playlistItems: PlaylistItemsInfo
