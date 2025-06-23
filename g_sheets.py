import streamlit as st
import gspread
import pandas as pd

@st.cache_resource(show_spinner=False)
def get_gspread_client():
    # Menggunakan method standar gspread tanpa perlu patch atau subclass
    return gspread.service_account_from_dict(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
    )

@st.cache_data(ttl=600, show_spinner=False)
def get_data(worksheet_name):
    try:
        client = get_gspread_client()
        ws = client.open("Data UMKM Gading Kirana").worksheet(worksheet_name)
        return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.error(f"❌ Gagal mengambil data Google Sheets: {e}")
        return pd.DataFrame()

@st.cache_resource(show_spinner=False)
def get_worksheet(worksheet_name):
    try:
        client = get_gspread_client()
        return client.open("Data UMKM Gading Kirana").worksheet(worksheet_name)
    except Exception as e:
        st.error(f"❌ Gagal mendapatkan worksheet: {e}")
        return None
