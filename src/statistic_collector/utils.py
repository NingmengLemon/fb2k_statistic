from collections.abc import Callable
import functools
import re
import hashlib
import asyncio
from typing import TypeVar, ParamSpec, Protocol
from collections.abc import Awaitable


###### From Meloland/melobot by @aicorein, modified ######
#: 泛型 T，无约束
T = TypeVar("T")
#: 泛型 T_co，协变无约束
T_co = TypeVar("T_co", covariant=True)
#: :obj:`~typing.ParamSpec` 泛型 P，无约束
P = ParamSpec("P")


class AsyncCallable(Protocol[P, T_co]):
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Awaitable[T_co]: ...


def lock() -> Callable[[AsyncCallable[P, T]], AsyncCallable[P, T]]:
    """锁装饰器"""
    alock = asyncio.Lock()

    def deco_func(func: AsyncCallable[P, T]) -> AsyncCallable[P, T]:

        @functools.wraps(func)
        async def wrapped_func(*args: P.args, **kwargs: P.kwargs) -> T:
            async with alock:
                return await func(*args, **kwargs)

        return wrapped_func

    return deco_func


##### melobot end ######


def handle_artist_field(
    artist_field: list[str] | str, delimiters: list[str], exclusions: list[str]
):
    if isinstance(artist_field, list) and len(artist_field) != 1:
        return artist_field
    if isinstance(artist_field, str):
        artist_field = [artist_field]
    for delimiter in delimiters:
        # 逐个检查分割符是否有效果
        if (
            len(
                result := split_with_exclusions(
                    artist_field[0],
                    delimiter,
                    exclusions,
                )
            )
            > 1
        ):
            return [r.strip() for r in result]
    # 都没有就算了
    return artist_field


def split_with_exclusions(
    s: str,
    delimiter: str,
    exclusions: list[str] | None = None,
    ignore_case: bool = False,
) -> list[str]:
    """Powered by ChatGPT"""
    if not exclusions:
        return s.split(delimiter)

    # Create a regex pattern for exclusions or the delimiter
    exclusion_pattern = "|".join(
        f"({re.escape(exclusion)})" for exclusion in exclusions
    )
    regex_pattern = f"({exclusion_pattern})|{re.escape(delimiter)}"

    # Custom split logic
    parts = []
    buffer = []
    last_end = 0  # Track the end of the last match
    for match in re.finditer(
        regex_pattern, s, re.IGNORECASE if ignore_case else re.NOFLAG
    ):
        start, end = match.span()

        # Append content before the match
        if start > last_end:
            buffer.append(s[last_end:start])

        if match.group(1):  # Match is an excluded substring
            if buffer:
                parts.append("".join(buffer))
                buffer = []
            parts.append(match.group(1))
        else:  # Match is the delimiter
            if buffer:
                parts.append("".join(buffer))
                buffer = []

        # Update last_end
        last_end = end

    # Handle remaining part of the string
    if last_end < len(s):
        buffer.append(s[last_end:])

    if buffer:
        parts.append("".join(buffer))

    return [part for part in parts if part]  # Remove empty parts if necessary
    # return parts


def calc_music_id(metadata: dict[str, str], *fields: str):
    return hashlib.sha256(
        ("-".join(str(metadata.get(f)) for f in fields)).encode("utf-8")
    ).hexdigest()
