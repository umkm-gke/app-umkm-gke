import streamlit as st
import bcrypt
from g_sheets import get_data

def login_form():
    """Menampilkan form login dan menangani logika autentikasi."""
    st.header("Portal Penjual: Login")

    vendors_df = get_data("Vendors")
    if vendors_df.empty:
        st.error("Tidak dapat memuat data penjual. Periksa koneksi Google Sheets.")
        return

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            # Cari vendor berdasarkan username
            vendor_data = vendors_df[vendors_df['username'] == username]

            if not vendor_data.empty:
                # Ambil password hash dari dataframe
                hashed_password_str = vendor_data.iloc['password_hash']
                hashed_password_bytes = hashed_password_str.encode('utf-8')

                # Verifikasi password
                if bcrypt.checkpw(password.encode('utf-8'), hashed_password_bytes):
                    st.session_state['logged_in'] = True
                    st.session_state['vendor_id'] = vendor_data.iloc['vendor_id']
                    st.session_state['vendor_name'] = vendor_data.iloc['vendor_name']
                    st.success(f"Login berhasil! Selamat datang, {st.session_state['vendor_name']}.")
                    st.rerun() # Muat ulang halaman untuk menampilkan dashboard
                else:
                    st.error("Username atau password salah.")
            else:
                st.error("Username atau password salah.")

def logout():
    """Menangani logika logout."""
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            if key in ['logged_in', 'vendor_id', 'vendor_name']:
                del st.session_state[key]
        st.rerun()
