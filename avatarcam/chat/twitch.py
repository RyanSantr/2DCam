from __future__ import annotations

from dataclasses import dataclass
import queue
import socket
import threading
import time


@dataclass
class ChatMessage:
    user: str
    text: str


class TwitchChatClient:
    """Cliente Twitch IRC anonimo para ler chat publico sem OAuth."""

    def __init__(self) -> None:
        self.messages: queue.Queue[ChatMessage] = queue.Queue(maxsize=80)
        self.events: queue.Queue[str] = queue.Queue(maxsize=20)
        self.channel = ""
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def start(self, channel: str) -> None:
        clean_channel = channel.strip().lower().lstrip("#")
        if not clean_channel:
            raise ValueError("Informe o canal da Twitch")
        self.stop()
        self.channel = clean_channel
        self._running.set()
        self._thread = threading.Thread(target=self._run, name="TwitchChat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

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
            self._connect()
            buffer = ""
            while self._running.is_set() and self._sock:
                chunk = self._sock.recv(4096).decode("utf-8", errors="ignore")
                if not chunk:
                    break
                buffer += chunk
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    self._handle_line(line)
        except Exception as exc:
            self._put_event(f"Chat Twitch desconectado: {exc}")
        finally:
            self.stop()

    def _connect(self) -> None:
        sock = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=12)
        sock.settimeout(1.0)
        nick = f"justinfan{int(time.time()) % 100000}"
        sock.sendall(f"PASS SCHMOOPIIE\r\nNICK {nick}\r\nJOIN #{self.channel}\r\n".encode("utf-8"))
        self._sock = sock
        self._put_event(f"Conectado ao chat: #{self.channel}")

    def _handle_line(self, line: str) -> None:
        if line.startswith("PING"):
            if self._sock:
                self._sock.sendall(b"PONG :tmi.twitch.tv\r\n")
            return
        if " PRIVMSG " not in line:
            return
        prefix, text = line.split(" PRIVMSG ", 1)
        if " :" not in text:
            return
        user = prefix.split("!", 1)[0].lstrip(":") or "chat"
        message = text.split(" :", 1)[1].strip()
        self._put_message(ChatMessage(user=user, text=message))

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
