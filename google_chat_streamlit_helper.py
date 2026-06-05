import json
import os
import tempfile

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/chat.messages.create"]


def _load_json_secret(secret_name: str) -> dict:
    raw = st.secrets.get(secret_name, "")
    if not raw:
        raise RuntimeError(f"Secret ausente: {secret_name}")
    return json.loads(raw)


def get_chat_service():
    token_data = _load_json_secret("GOOGLE_CHAT_TOKEN_JSON")
    client_data = _load_json_secret("GOOGLE_CHAT_CLIENT_SECRET_JSON")

    # Compatibilidade com tokens exportados como access_token em vez de token.
    if "token" not in token_data and "access_token" in token_data:
        value = token_data["access_token"]
        token_data["token"] = value[0] if isinstance(value, list) else value

    # Compatibilidade com refresh_token salvo como lista.
    if isinstance(token_data.get("refresh_token"), list):
        token_data["refresh_token"] = token_data["refresh_token"][0]

    key = "installed" if "installed" in client_data else "web"
    client_info = client_data[key]

    token_data.setdefault("client_id", client_info["client_id"])
    token_data.setdefault("client_secret", client_info["client_secret"])
    token_data.setdefault("token_uri", client_info.get("token_uri", "https://oauth2.googleapis.com/token"))
    token_data.setdefault("scopes", SCOPES)

    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                raise RuntimeError(
                    "Token do Google Chat expirou e não foi possível renovar. "
                    "Gere um novo GOOGLE_CHAT_TOKEN_JSON localmente e atualize o Streamlit Secrets."
                ) from exc
        else:
            raise RuntimeError(
                "Token do Google Chat inválido. Gere um novo GOOGLE_CHAT_TOKEN_JSON localmente."
            )

    return build("chat", "v1", credentials=creds)


def get_default_space_id() -> str:
    space_id = st.secrets.get("GOOGLE_CHAT_SPACE_ID", "").strip()
    if not space_id:
        raise RuntimeError("Secret ausente: GOOGLE_CHAT_SPACE_ID")
    return space_id


def send_google_chat_text(textbody: str, space_id: str | None = None):
    service = get_chat_service()
    parent = space_id or get_default_space_id()

    return service.spaces().messages().create(
        parent=parent,
        body={"text": textbody},
    ).execute()


def send_google_chat_file(
    textbody: str,
    file_path: str,
    filename: str | None = None,
    mimetype: str = "image/png",
    space_id: str | None = None,
):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    if filename is None:
        filename = os.path.basename(file_path)

    service = get_chat_service()
    parent = space_id or get_default_space_id()

    media = MediaFileUpload(file_path, mimetype=mimetype)

    attachment_uploaded = service.media().upload(
        parent=parent,
        body={"filename": filename},
        media_body=media,
    ).execute()

    return service.spaces().messages().create(
        parent=parent,
        body={
            "text": textbody,
            "attachment": [attachment_uploaded],
        },
    ).execute()


def send_google_chat_image(textbody: str, image_path: str, space_id: str | None = None):
    ext = os.path.splitext(image_path)[1].lower()

    if ext in [".jpg", ".jpeg"]:
        mimetype = "image/jpeg"
    elif ext == ".png":
        mimetype = "image/png"
    elif ext == ".gif":
        mimetype = "image/gif"
    elif ext == ".webp":
        mimetype = "image/webp"
    else:
        raise ValueError(f"Extensão de imagem não suportada: {ext}")

    return send_google_chat_file(
        textbody=textbody,
        file_path=image_path,
        filename=os.path.basename(image_path),
        mimetype=mimetype,
        space_id=space_id,
    )
