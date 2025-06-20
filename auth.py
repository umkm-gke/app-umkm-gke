import streamlit as st
import bcrypt
from g_sheets import get_data

def login_form():
    """Menampilkan form login dan menangani logika autentikasi."""
    st.header("Silakan Log in")
    vendors_df = get_data("Vendors")

    if vendors_df.empty:
        st.error("Tidak dapat memuat data penjual. Periksa koneksi Google Sheets.")
        return

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            # Login Admin
            if username == "admin" and password == "admin123":
                st.session_state['logged_in'] = True
                st.session_state['is_admin'] = True
                st.session_state['vendor_name'] = "Administrator"
                st.session_state['vendor_id'] = None
                st.session_state['role'] = 'admin'
                st.success("✅ Login sebagai Admin")
                st.rerun()

            # Login Vendor
            vendor_data = vendors_df[vendors_df['username'] == username]

            if not vendor_data.empty:
                hashed_password_str = vendor_data['password_hash'].values[0]
                hashed_password_bytes = hashed_password_str.encode('utf-8')
                status = vendor_data['status'].values[0] if 'status' in vendor_data.columns else 'pending'

                if bcrypt.checkpw(password.encode('utf-8'), hashed_password_bytes):
                    status_lower = status.lower()
                    if status_lower == 'pending':
                        st.warning("⏳ Akun Anda belum disetujui. Silakan hubungi admin.")
                        return
                    elif status_lower == 'rejected':
                        st.error("❌ Akun Anda telah ditolak. Silakan hubungi admin untuk informasi lebih lanjut.")
                        return
                    elif status_lower != 'approved':
                        st.warning("Status akun tidak valid. Silakan hubungi admin.")
                        return

                    st.session_state['logged_in'] = True
                    st.session_state['is_admin'] = False
                    st.session_state['vendor_id'] = vendor_data['vendor_id'].values[0]
                    st.session_state['vendor_name'] = vendor_data['vendor_name'].values[0]
                    st.session_state['role'] = 'vendor'
                    st.success(f"✅ Login berhasil! Selamat datang, {st.session_state['vendor_name']}.")
                    st.rerun()
                else:
                    st.error("❌ Username atau password salah.")
            else:
                st.error("❌ Username atau password salah.")

def logout():
    """Menangani logika logout."""
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            if key in ['logged_in', 'vendor_id', 'vendor_name', 'is_admin', 'role']:
                del st.session_state[key]
        st.rerun()
