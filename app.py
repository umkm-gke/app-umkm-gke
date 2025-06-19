import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
import json
from urllib.parse import quote_plus
import bcrypt # Diperlukan untuk hashing password pendaftaran

from g_sheets import get_data, get_worksheet
from auth import login_form, logout

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Marketplace UMKM Warga", layout="wide")

# --- INISIALISASI SESSION STATE ---
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- FUNGSI BANTU ---
def add_to_cart(product):
    """Menambahkan produk ke keranjang belanja."""
    for item in st.session_state.cart:
        if item['product_id'] == product['product_id']:
            item['quantity'] += 1
            st.toast(f"Jumlah {product['product_name']} ditambah!", icon="🛒")
            return
    
    new_item = {
        'product_id': product['product_id'],
        'product_name': product['product_name'],
        'price': product['price'],
        'vendor_id': product['vendor_id'],
        'quantity': 1
    }
    st.session_state.cart.append(new_item)
    st.toast(f"{product['product_name']} ditambahkan ke keranjang!", icon="✅")

# --- TAMPILAN UTAMA ---
st.title("🏡 GKE Marketplace")
st.write("Temukan produk UMKM terbaik dari tetangga Anda!")

# --- NAVIGASI ---
# Menambahkan opsi "Daftar sebagai Penjual"
menu_selection = st.sidebar.radio(
    "Menu Navigasi",
   
)

# =================================================================
# --- HALAMAN BELANJA ---
# =================================================================
if menu_selection == "Belanja":
    st.header("🛍️ Katalog Produk")
    
    products_df = get_data("Products")
    vendors_df = get_data("Vendors")

    if products_df.empty or vendors_df.empty:
        st.warning("Gagal memuat produk atau data penjual. Silakan coba lagi nanti.")
    else:
        products_df = pd.merge(products_df, vendors_df[['vendor_id', 'vendor_name']], on='vendor_id', how='left')
        active_products = products_df[products_df['is_active'] == True]

        if active_products.empty:
            st.info("Saat ini belum ada produk yang tersedia.")
        else:
            cols = st.columns(3)
            for index, product in active_products.iterrows():
                col = cols[index % 3]
                with col:
                    with st.container(border=True):
                        st.image(product['image_url'], caption=product['product_name'])
                        st.subheader(product['product_name'])
                        st.write(f"**Rp {product['price']:,}**")
                        st.write(f"Oleh: **{product['vendor_name']}**")
                        st.write(product['description'])
                        if st.button("🛒 Tambah ke Keranjang", key=f"add_{product['product_id']}"):
                            add_to_cart(product)

# =================================================================
# --- HALAMAN KERANJANG BELANJA ---
# =================================================================
elif menu_selection == "Keranjang Belanja":
    st.header("🛒 Keranjang Belanja Anda")
    
    if not st.session_state.cart:
        st.info("Keranjang Anda masih kosong. Yuk, mulai belanja!")
    else:
        total_price = 0
        vendors_in_cart = {}

        for i, item in enumerate(st.session_state.cart):
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    st.subheader(item['product_name'])
                    st.write(f"Rp {item['price']:,}")
                with col2:
                    new_quantity = st.number_input("Jumlah", min_value=1, value=item['quantity'], key=f"qty_{i}")
                    st.session_state.cart[i]['quantity'] = new_quantity
                with col3:
                    subtotal = item['price'] * item['quantity']
                    st.metric("Subtotal", f"Rp {subtotal:,}")
                with col4:
                    if st.button("Hapus", key=f"del_{i}"):
                        st.session_state.cart.pop(i)
                        st.rerun()
            
            total_price += subtotal
            vendor_id = item['vendor_id']
            if vendor_id not in vendors_in_cart:
                vendors_in_cart[vendor_id] = 0
            vendors_in_cart[vendor_id] += subtotal

        st.header(f"Total Belanja: Rp {total_price:,}")

        st.subheader("📝 Lanjutkan Pemesanan")
        with st.form("checkout_form"):
            customer_name = st.text_input("Nama Anda")
            customer_contact = st.text_input("Nomor HP Anda (untuk konfirmasi)")
            
            submit_order = st.form_submit_button("Buat Pesanan Sekarang")

            if submit_order:
                if not customer_name or not customer_contact:
                    st.warning("Nama dan Nomor HP tidak boleh kosong.")
                else:
                    with st.spinner("Memproses pesanan..."):
                        orders_ws = get_worksheet("Orders")
                        vendors_df = get_data("Vendors")
                        
                        if orders_ws is None or vendors_df.empty:
                            st.error("Gagal memproses pesanan. Coba lagi.")
                        else:
                            order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
                            order_details_json = json.dumps(st.session_state.cart)
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            new_order_row = [order_id, customer_name, customer_contact, order_details_json, total_price, "New", timestamp]
                            orders_ws.append_row(new_order_row)
                            
                            st.success(f"Pesanan Anda ({order_id}) berhasil dibuat!")
                            st.balloons()

                            st.subheader("Rincian Tagihan & Konfirmasi Pesanan")
                            st.info("Silakan lakukan pembayaran ke masing-masing penjual dan konfirmasi pesanan dengan mengklik tombol WhatsApp di bawah ini.")

                            for vendor_id, amount in vendors_in_cart.items():
                                vendor_info = vendors_df[vendors_df['vendor_id'] == vendor_id].iloc
                                items_from_vendor = [f"{item['quantity']}x {item['product_name']}" for item in st.session_state.cart if item['vendor_id'] == vendor_id]
                                message = (
                                    f"Halo {vendor_info['vendor_name']}, saya {customer_name} ingin konfirmasi pesanan {order_id}.\n\n"
                                    f"Pesanan saya:\n"
                                    f"{', '.join(items_from_vendor)}\n\n"
                                    f"Total: Rp {amount:,}\n"
                                    f"Terima kasih!"
                                )
                                encoded_message = quote_plus(message)
                                whatsapp_url = f"https://wa.me/{vendor_info['whatsapp_number']}?text={encoded_message}"
                                
                                st.write(f"---")
                                st.write(f"**Penjual: {vendor_info['vendor_name']}**")
                                st.write(f"**Total Tagihan: Rp {amount:,}**")
                                st.write(f"**Pembayaran:** (Tambahkan info rekening di sini)")
                                st.link_button(f"💬 Konfirmasi ke {vendor_info['vendor_name']} via WhatsApp", whatsapp_url)

                            st.session_state.cart =

# =================================================================
# --- HALAMAN PORTAL PENJUAL ---
# =================================================================
elif menu_selection == "Portal Penjual":
    if not st.session_state.get('logged_in'):
        login_form()
    else:
        st.sidebar.success(f"Login sebagai: **{st.session_state['vendor_name']}**")
        logout()
        
        st.header(f"Dashboard: {st.session_state['vendor_name']}")
        st.subheader("📦 Produk Anda")
        
        products_df = get_data("Products")
        my_products = products_df[products_df['vendor_id'] == st.session_state['vendor_id']]

        if my_products.empty:
            st.info("Anda belum memiliki produk. Silakan tambahkan produk baru.")
        else:
            st.dataframe(my_products)

        with st.expander("➕ Tambah atau Edit Produk"):
            with st.form("product_form", clear_on_submit=True):
                product_id_to_edit = st.text_input("ID Produk (kosongkan untuk menambah produk baru)")
                product_name = st.text_input("Nama Produk")
                description = st.text_area("Deskripsi")
                price = st.number_input("Harga", min_value=0)
                image_url = st.text_input("URL Gambar Produk")
                stock_quantity = st.number_input("Jumlah Stok", min_value=0)
                is_active = st.checkbox("Tampilkan Produk?", value=True)
                
                submitted = st.form_submit_button("Simpan Produk")

                if submitted:
                    products_ws = get_worksheet("Products")
                    if products_ws:
                        if product_id_to_edit:
                            cell = products_ws.find(product_id_to_edit)
                            if cell:
                                row_to_update = cell.row
                                update_data = [product_id_to_edit, st.session_state['vendor_id'], product_name, description, price, image_url, stock_quantity, is_active, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                                products_ws.update(f'A{row_to_update}:I{row_to_update}', [update_data])
                                st.success(f"Produk {product_name} berhasil diperbarui!")
                            else:
                                st.error("ID Produk tidak ditemukan.")
                        else:
                            new_product_id = f"PROD-{uuid.uuid4().hex[:6].upper()}"
                            new_row = [new_product_id, st.session_state['vendor_id'], product_name, description, price, image_url, stock_quantity, is_active, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                            products_ws.append_row(new_row)
                            st.success(f"Produk baru '{product_name}' berhasil ditambahkan!")
                        
                        st.cache_data.clear()
                        st.rerun()

# =================================================================
# --- HALAMAN PENDAFTARAN VENDOR (BARU) ---
# =================================================================
elif menu_selection == "Daftar sebagai Penjual":
    st.header("✍️ Pendaftaran Penjual Baru")
    st.write("Isi formulir di bawah ini untuk mulai berjualan di platform kami.")

    with st.form("vendor_registration_form", clear_on_submit=True):
        vendor_name = st.text_input("Nama Toko / UMKM Anda")
        username = st.text_input("Username (untuk login)")
        whatsapp_number = st.text_input("Nomor WhatsApp (format: 628xxxxxxxxxx)")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Konfirmasi Password", type="password")
        
        submitted = st.form_submit_button("Daftar Sekarang")

        if submitted:
            # Validasi input
            if not all([vendor_name, username, whatsapp_number, password, confirm_password]):
                st.warning("Semua kolom wajib diisi.")
            elif password!= confirm_password:
                st.error("Password dan konfirmasi password tidak cocok.")
            else:
                with st.spinner("Mendaftarkan akun Anda..."):
                    vendors_df = get_data("Vendors")
                    
                    # Cek apakah username sudah ada
                    if not vendors_df.empty and username in vendors_df['username'].values:
                        st.error("Username ini sudah digunakan. Silakan pilih yang lain.")
                    else:
                        vendors_ws = get_worksheet("Vendors")
                        if vendors_ws:
                            # Buat data vendor baru
                            vendor_id = f"VEND-{uuid.uuid4().hex[:6].upper()}"
                            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                            
                            new_vendor_row = [vendor_id, vendor_name, username, hashed_password, whatsapp_number]
                            
                            # Tambahkan ke Google Sheets
                            vendors_ws.append_row(new_vendor_row)
                            
                            st.success(f"Pendaftaran berhasil! Selamat datang, {vendor_name}. Silakan login melalui 'Portal Penjual'.")
                            st.balloons()
                            
                            # Hapus cache agar data vendor yang baru bisa langsung terbaca
                            st.cache_data.clear()
                        else:
                            st.error("Gagal terhubung ke database. Coba lagi nanti.")
