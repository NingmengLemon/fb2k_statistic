"""仿照 aiosseclient 弄了个自己习惯的"""

from dataclasses import dataclass


@dataclass
class Event:
    id: str | None = None
    event: str = "message"
    data: str = ""
    retry: int | None = None


def parse_sse_message(sse_message: str) -> Event:
    event = Event()
    for line in sse_message.splitlines():
        if line.startswith(":"):
            continue
        if ":" in line:
            field, value = line.split(":", 1)
            value = value.lstrip()  # 去除值前空格
        else:
            field, value = line, ""
        field = field.strip()

        if field == "id":
            event.id = value
        elif field == "event":
            event.event = value
        elif field == "data":
            event.data += value + "\n"  # 拼接多行 data
        elif field == "retry":
            try:
                event.retry = int(value)
            except ValueError:
                pass

    event.data = event.data.rstrip("\n")
    return event
