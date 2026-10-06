from __future__ import annotations

import html
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from requests_oauthlib import OAuth1

X_API_BASE = "https://api.x.com/2"
TELEGRAM_API_BASE = "https://api.telegram.org"
ISTANBUL = ZoneInfo("Europe/Istanbul")


class RelayError(RuntimeError):
    pass


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "evet"}


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RelayError(f"Eksik ortam değişkeni: {name}")
    return value


@dataclass(frozen=True)
class Config:
    x_api_key: str
    x_api_secret: str
    x_access_token: str
    x_access_token_secret: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_topic_id: str | None
    state_path: Path
    exclude_replies: bool
    exclude_retweets: bool
    protect_content: bool
    bootstrap_send_latest: bool

    @classmethod
    def from_env(cls) -> Config:
        topic = os.getenv("TELEGRAM_TOPIC_ID", "").strip() or None
        return cls(
            x_api_key=required_env("X_API_KEY"),
            x_api_secret=required_env("X_API_SECRET"),
            x_access_token=required_env("X_ACCESS_TOKEN"),
            x_access_token_secret=required_env("X_ACCESS_TOKEN_SECRET"),
            telegram_bot_token=required_env("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=required_env("TELEGRAM_CHAT_ID"),
            telegram_topic_id=topic,
            state_path=Path(os.getenv("X_RELAY_STATE_PATH", "state/last_seen.json")),
            exclude_replies=env_bool("X_EXCLUDE_REPLIES", True),
            exclude_retweets=env_bool("X_EXCLUDE_RETWEETS", True),
            protect_content=env_bool("TELEGRAM_PROTECT_CONTENT", True),
            bootstrap_send_latest=env_bool("X_RELAY_BOOTSTRAP_SEND_LATEST", False),
        )


class XClient:
    def __init__(self, config: Config):
        self.session = requests.Session()
        self.session.auth = OAuth1(
            config.x_api_key,
            config.x_api_secret,
            config.x_access_token,
            config.x_access_token_secret,
        )

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(f"{X_API_BASE}{path}", params=params, timeout=30)
        if not response.ok:
            raise RelayError(f"X API hatası {response.status_code}: {response.text[:800]}")
        payload = response.json()
        if payload.get("errors") and not payload.get("data"):
            raise RelayError(
                f"X API hata yanıtı: "
                f"{json.dumps(payload['errors'], ensure_ascii=False)[:800]}"
            )
        return payload

    def me(self) -> dict[str, Any]:
        payload = self._get(
            "/users/me",
            params={"user.fields": "username,name,protected"},
        )
        data = payload.get("data")
        if not data:
            raise RelayError("X API /users/me yanıtında kullanıcı bulunamadı.")
        return data

    def posts(
        self,
        user_id: str,
        *,
        since_id: str | None,
        exclude_replies: bool,
        exclude_retweets: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        params: dict[str, Any] = {
            "max_results": 10,
            "tweet.fields": "created_at,attachments,referenced_tweets,note_tweet",
            "expansions": "attachments.media_keys",
            "media.fields": (
                "media_key,type,url,preview_image_url,variants,width,height,alt_text"
            ),
        }
        excludes: list[str] = []
        if exclude_replies:
            excludes.append("replies")
        if exclude_retweets:
            excludes.append("retweets")
        if excludes:
            params["exclude"] = ",".join(excludes)
        if since_id:
            params["since_id"] = since_id

        payload = self._get(f"/users/{user_id}/tweets", params=params)
        posts = payload.get("data") or []
        media = {
            item["media_key"]: item
            for item in (payload.get("includes", {}).get("media") or [])
            if item.get("media_key")
        }
        return posts, media


class TelegramClient:
    def __init__(
        self,
        token: str,
        chat_id: str,
        topic_id: str | None,
        protect_content: bool,
    ):
        self.base = f"{TELEGRAM_API_BASE}/bot{token}"
        self.chat_id = chat_id
        self.topic_id = topic_id
        self.protect_content = protect_content
        self.session = requests.Session()

    def _common(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "protect_content": self.protect_content,
        }
        if self.topic_id:
            payload["message_thread_id"] = int(self.topic_id)
        return payload

    def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base}/{method}",
            json=payload,
            timeout=60,
        )
        if not response.ok:
            raise RelayError(
                f"Telegram {method} hatası {response.status_code}: "
                f"{response.text[:800]}"
            )
        body = response.json()
        if not body.get("ok"):
            raise RelayError(
                f"Telegram {method} başarısız: "
                f"{json.dumps(body, ensure_ascii=False)[:800]}"
            )
        return body

    @staticmethod
    def _button(post_url: str) -> dict[str, Any]:
        return {
            "inline_keyboard": [[{"text": "𝕏'te görüntüle", "url": post_url}]]
        }

    def send_text(self, rendered_html: str, post_url: str) -> None:
        chunks = split_html_message(rendered_html)
        for index, chunk in enumerate(chunks):
            payload = self._common()
            payload.update(
                {
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }
            )
            if index == len(chunks) - 1:
                payload["reply_markup"] = self._button(post_url)
            self._post("sendMessage", payload)

    def send_post(
        self,
        rendered_html: str,
        post_url: str,
        media_items: list[dict[str, str]],
    ) -> None:
        if not media_items:
            self.send_text(rendered_html, post_url)
            return

        text_sent = False
        if len(rendered_html) > 900:
            self.send_text(rendered_html, post_url)
            text_sent = True
            caption = None
        else:
            caption = rendered_html

        try:
            if len(media_items) == 1:
                item = media_items[0]
                payload = self._common()
                field = "photo" if item["type"] == "photo" else "video"
                payload[field] = item["url"]
                if caption:
                    payload["caption"] = caption
                    payload["parse_mode"] = "HTML"
                    payload["reply_markup"] = self._button(post_url)
                method = "sendPhoto" if item["type"] == "photo" else "sendVideo"
                self._post(method, payload)
                return

            media_payload: list[dict[str, Any]] = []
            for index, item in enumerate(media_items[:10]):
                row: dict[str, Any] = {
                    "type": item["type"],
                    "media": item["url"],
                }
                if index == 0 and caption:
                    linked_caption = (
                        f'{caption}\n\n<a href="{html.escape(post_url)}">'
                        "𝕏'te görüntüle</a>"
                    )
                    row["caption"] = linked_caption
                    row["parse_mode"] = "HTML"
                media_payload.append(row)

            payload = self._common()
            payload["media"] = media_payload
            self._post("sendMediaGroup", payload)
        except RelayError:
            if not text_sent:
                self.send_text(rendered_html, post_url)
            else:
                print(
                    "UYARI: Metin gönderildi ancak medya Telegram tarafından "
                    "alınamadı.",
                    file=sys.stderr,
                )


def post_text(post: dict[str, Any]) -> str:
    note = post.get("note_tweet") or {}
    return (note.get("text") or post.get("text") or "").strip()


def post_url(username: str, post_id: str) -> str:
    return f"https://x.com/{username}/status/{post_id}"


def format_time(value: str | None) -> str:
    if not value:
        return ""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ISTANBUL)
    return dt.strftime("%d.%m.%Y %H:%M")


def render_post_html(
    username: str,
    post: dict[str, Any],
    protected: bool,
) -> str:
    lock = " 🔒" if protected else ""
    body = html.escape(post_text(post)) or "<i>Metinsiz gönderi</i>"
    timestamp = format_time(post.get("created_at"))
    parts = [f"<b>𝕏 @{html.escape(username)}{lock}</b>", "", body]
    if timestamp:
        parts.extend(["", f"🕒 {timestamp}"])
    return "\n".join(parts)


def best_video_url(media: dict[str, Any]) -> str | None:
    candidates = []
    for variant in media.get("variants") or []:
        url = variant.get("url")
        content_type = variant.get("content_type", "")
        if url and content_type == "video/mp4":
            candidates.append((int(variant.get("bit_rate") or 0), url))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    return media.get("preview_image_url")


def media_for_post(
    post: dict[str, Any],
    media_by_key: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for key in post.get("attachments", {}).get("media_keys", [])[:10]:
        media = media_by_key.get(key)
        if not media:
            continue
        kind = media.get("type")
        if kind == "photo" and media.get("url"):
            output.append({"type": "photo", "url": media["url"]})
        elif kind in {"video", "animated_gif"}:
            url = best_video_url(media)
            if url:
                output.append({"type": "video", "url": url})
    return output


def split_html_message(rendered: str, limit: int = 3900) -> list[str]:
    if len(rendered) <= limit:
        return [rendered]
    chunks: list[str] = []
    remaining = rendered
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def load_state(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"initialized": False, "last_seen_id": None}
    except (json.JSONDecodeError, OSError):
        return {"initialized": False, "last_seen_id": None}
    return {
        "initialized": bool(payload.get("initialized")),
        "last_seen_id": (
            str(payload["last_seen_id"]) if payload.get("last_seen_id") else None
        ),
    }


def save_state(path: Path, post_id: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(
            {
                "initialized": True,
                "last_seen_id": str(post_id) if post_id else None,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    tmp.replace(path)


def main() -> int:
    try:
        config = Config.from_env()
        x = XClient(config)
        me = x.me()
        username = me["username"]
        user_id = me["id"]
        protected = bool(me.get("protected"))
        state = load_state(config.state_path)
        last_seen = state["last_seen_id"]

        posts, media_map = x.posts(
            user_id,
            since_id=last_seen,
            exclude_replies=config.exclude_replies,
            exclude_retweets=config.exclude_retweets,
        )
        posts = sorted(posts, key=lambda item: int(item["id"]))

        if not state["initialized"]:
            if posts and config.bootstrap_send_latest:
                posts = [posts[-1]]
            else:
                newest_id = posts[-1]["id"] if posts else None
                save_state(config.state_path, newest_id)
                if newest_id:
                    print(
                        "İlk çalıştırma: geçmiş gönderiler atlandı, "
                        f"başlangıç ID={newest_id}"
                    )
                else:
                    print(
                        "İlk çalıştırma: hesapta gönderi yok; başlangıç durumu "
                        "oluşturuldu."
                    )
                return 0

        telegram = TelegramClient(
            config.telegram_bot_token,
            config.telegram_chat_id,
            config.telegram_topic_id,
            config.protect_content,
        )

        sent = 0
        for post in posts:
            url = post_url(username, post["id"])
            rendered = render_post_html(username, post, protected)
            media_items = media_for_post(post, media_map)
            telegram.send_post(rendered, url, media_items)
            save_state(config.state_path, post["id"])
            sent += 1
            print(f"Gönderildi: {post['id']}")

        if not posts:
            print("Yeni X gönderisi yok.")
        else:
            print(f"Toplam {sent} yeni gönderi Telegram'a aktarıldı.")
        return 0
    except (RelayError, requests.RequestException, ValueError, OSError, KeyError) as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
