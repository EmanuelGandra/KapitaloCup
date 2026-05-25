import os
from typing import Optional

import pandas as pd
import streamlit as st
from supabase import create_client, Client


def _get_secret(name: str) -> str:
    """
    Primeiro tenta variável de ambiente.
    Depois tenta .streamlit/secrets.toml.
    """
    env_value = os.getenv(name)
    if env_value:
        return env_value

    return st.secrets[name]


def get_supabase() -> Client:
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_KEY")
    return create_client(url, key)


@st.cache_resource
def get_supabase_client() -> Client:
    return get_supabase()


def get_client() -> Client:
    """
    Alias usado pelo app.py e pelo auth.py.
    """
    return get_supabase()


def fetch_df(
    table_name: str,
    select: str = "*",
    order_by: Optional[str] = None,
    ascending: bool = True,
) -> pd.DataFrame:
    """
    Lê uma tabela do Supabase e devolve como pandas DataFrame.

    Exemplo:
        matches = fetch_df("matches", order_by="match_no")
    """
    supabase = get_client()

    query = supabase.table(table_name).select(select)

    if order_by:
        query = query.order(order_by, desc=not ascending)

    result = query.execute()

    if not result.data:
        return pd.DataFrame()

    return pd.DataFrame(result.data)