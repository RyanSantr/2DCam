from __future__ import annotations

from dataclasses import dataclass
import json
import queue
import re
import threading
import time
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen


@dataclass
class ChatMessage:
    user: str
    text: str


class YouTubeChatClient:
    """Cliente leve para YouTube Live Chat usando YouTube Data API v3."""

    API_ROOT = "https://www.googleapis.com/youtube/v3"

    def __init__(self) -> None:
        self.messages: queue.Queue[ChatMessage] = queue.Queue(maxsize=80)
        self.events: queue.Queue[str] = queue.Queue(maxsize=20)
        self._thread: threading.Thread | None = None
        self._running = threading.Event()
        self._api_key = ""
        self._video_or_chat_id = ""
        self._live_chat_id = ""

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def start(self, video_or_chat_id: str, api_key: str, live_chat_id: str = "") -> None:
        clean_api_key = api_key.strip()
        clean_target = video_or_chat_id.strip()
        clean_chat_id = live_chat_id.strip()
        if not clean_api_key:
            raise ValueError("Informe a API key do YouTube")
        if not clean_target and not clean_chat_id:
            raise ValueError("Informe o ID/URL da live ou o liveChatId")
        self.stop()
        self._api_key = clean_api_key
        self._video_or_chat_id = clean_target
        self._live_chat_id = clean_chat_id
        self._running.set()
        self._thread = threading.Thread(target=self._run, name="YouTubeChat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()

    def drain_messages(self, limit: int = 20) -> list[ChatMessage]:
        items: list[ChatMessage] = []
        for _ in range(limit):
            try:
                items.append(self.messages.get_nowait())
            except queue.Empty:
                break
        return items

    def drain_events(self, limit: int = 10) -> list[str]:
        items: list[str] = []
        for _ in range(limit):
            try:
                items.append(self.events.get_nowait())
            except queue.Empty:
                break
        return items

    def _run(self) -> None:
        try:
            live_chat_id = self._live_chat_id or self._resolve_live_chat_id(self._video_or_chat_id)
            if not live_chat_id:
                raise ValueError("Nao encontrei liveChatId. Confira se a live esta ativa.")
            self._put_event("Conectado ao chat do YouTube")
            page_token = ""
            wait_seconds = 4.0
            while self._running.is_set():
                payload = self._request(
                    "liveChat/messages",
                    {
                        "part": "snippet,authorDetails",
                        "liveChatId": live_chat_id,
                        "maxResults": "50",
                        **({"pageToken": page_token} if page_token else {}),
                    },
                )
                page_token = payload.get("nextPageToken", page_token)
                wait_seconds = max(1.5, float(payload.get("pollingIntervalMillis", 4000)) / 1000)
                for item in payload.get("items", []):
                    snippet = item.get("snippet", {})
                    author = item.get("authorDetails", {})
                    text = snippet.get("displayMessage", "").strip()
                    user = author.get("displayName", "youtube")
                    if text:
                        self._put_message(ChatMessage(user=user, text=text))
                time.sleep(wait_seconds)
        except Exception as exc:
            self._put_event(f"Chat YouTube desconectado: {exc}")
        finally:
            self.stop()

    def _resolve_live_chat_id(self, video_or_url: str) -> str:
        video_id = self._extract_video_id(video_or_url)
        if not video_id:
            return video_or_url.strip()
        payload = self._request(
            "videos",
            {
                "part": "liveStreamingDetails",
                "id": video_id,
            },
        )
        items = payload.get("items", [])
        if not items:
            return ""
        details = items[0].get("liveStreamingDetails", {})
        return details.get("activeLiveChatId", "")

    def _extract_video_id(self, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        if re.fullmatch(r"[\w-]{11}", value):
            return value
        parsed = urlparse(value)
        if parsed.netloc.endswith("youtu.be"):
            return parsed.path.strip("/")
        query_id = parse_qs(parsed.query).get("v", [""])[0]
        if query_id:
            return query_id
        match = re.search(r"/live/([\w-]{11})", parsed.path)
        return match.group(1) if match else ""

    def _request(self, path: str, params: dict[str, str]) -> dict:
        url = f"{self.API_ROOT}/{path}?{urlencode({**params, 'key': self._api_key})}"
        with urlopen(url, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))

    def _put_message(self, message: ChatMessage) -> None:
        try:
            self.messages.put_nowait(message)
        except queue.Full:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                pass
            self.messages.put_nowait(message)

    def _put_event(self, text: str) -> None:
        try:
            self.events.put_nowait(text)
        except queue.Full:
            pass
