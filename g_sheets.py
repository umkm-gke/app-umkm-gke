import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

@st.cache_resource(show_spinner=False)
def get_gspread_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=600, show_spinner=False)  # cache data 10 menit
def get_data(worksheet_name):
    try:
        client = get_gspread_client()
        spreadsheet = client.open("Data UMKM Gading Kirana")
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Gagal terhubung ke Google Sheets: {e}")
        return pd.DataFrame()

@st.cache_resource(show_spinner=False)
def get_worksheet(worksheet_name):
    try:
        client = get_gspread_client()
        spreadsheet = client.open("Data UMKM Gading Kirana")
        return spreadsheet.worksheet(worksheet_name)
    except Exception as e:
        st.error(f"Gagal mendapatkan worksheet: {e}")
        return None
