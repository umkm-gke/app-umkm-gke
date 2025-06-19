import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# Menggunakan cache data untuk menghindari pemanggilan API berulang kali
@st.cache_data(show_spinner=False)
def get_data(worksheet_name):
    """Mengambil semua data dari worksheet tertentu dan mengembalikannya sebagai DataFrame."""
    try:
        # Menggunakan st.secrets untuk mengakses kredensial
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
        )
        client = gspread.authorize(creds)

        # Buka spreadsheet berdasarkan nama
        spreadsheet = client.open("Data UMKM Gading Kirana") # Ganti dengan nama spreadsheet Anda
        worksheet = spreadsheet.worksheet(worksheet_name)

        return pd.DataFrame(worksheet.get_all_records())
    except Exception as e:
        st.error(f"Gagal terhubung ke Google Sheets: {e}")
        return pd.DataFrame()

def get_worksheet(worksheet_name):
    """Mendapatkan objek worksheet untuk operasi tulis."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open("Data UMKM Gading Kirana") # Ganti dengan nama spreadsheet Anda
        return spreadsheet.worksheet(worksheet_name)
    except Exception as e:
        st.error(f"Gagal mendapatkan worksheet: {e}")
        return None
