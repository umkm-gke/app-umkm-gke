import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# Client GSpread dengan patch aman untuk kompatibilitas penuh
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    info = st.secrets["gcp_service_account"]
    
    class PatchedCredentials(Credentials):
        @property
        def access_token(self):
            return self.token

    # Patch kredensial agar gspread tidak error saat refresh token
    creds = PatchedCredentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

# Mengambil DataFrame dari worksheet tertentu
@st.cache_data(ttl=600, show_spinner=False)
def get_data(worksheet_name):
    try:
        client = get_gspread_client()
        spreadsheet = client.open("Data UMKM Gading Kirana")
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"❌ Gagal mengambil data dari Google Sheets: {e}")
        return pd.DataFrame()

# Mengambil worksheet (gspread Worksheet object)
@st.cache_resource(show_spinner=False)
def get_worksheet(worksheet_name):
    try:
        client = get_gspread_client()
        spreadsheet = client.open("Data UMKM Gading Kirana")
        return spreadsheet.worksheet(worksheet_name)
    except Exception as e:
        st.error(f"❌ Gagal mengambil worksheet: {e}")
        return None
