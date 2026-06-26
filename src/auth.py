import hashlib

import streamlit as st

from src.db import get_client


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()

    if not username:
        return False, "Informe um usuário."

    if not password:
        return False, "Informe uma senha."

    supabase = get_client()

    existing = (
        supabase.table("profiles")
        .select("id, username")
        .eq("username", username)
        .execute()
    )

    if existing.data:
        return False, "Esse usuário já existe."

    password_hash = hash_password(password)

    supabase.table("profiles").insert(
        {
            "username": username,
            "password_hash": password_hash,
        }
    ).execute()

    return True, "Usuário criado com sucesso."


def login_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()

    if not username or not password:
        return False, "Informe usuário e senha."

    supabase = get_client()
    password_hash = hash_password(password)

    result = (
        supabase.table("profiles")
        .select("id, username, password_hash")
        .eq("username", username)
        .execute()
    )

    if not result.data:
        return False, "Usuário não encontrado."

    user = result.data[0]

    if user["password_hash"] != password_hash:
        return False, "Senha inválida."

    st.session_state["user_id"] = user["id"]
    st.session_state["username"] = user["username"]
    st.session_state["is_logged_in"] = True

    return True, "Login realizado com sucesso."


def logout() -> None:
    st.session_state.pop("user_id", None)
    st.session_state.pop("username", None)
    st.session_state.pop("is_logged_in", None)
