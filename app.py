import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
import json
from urllib.parse import quote_plus
import bcrypt # Diperlukan untuk hashing password pendaftaran
import os

from g_sheets import get_data, get_worksheet
from auth import login_form, logout

from streamlit_option_menu import option_menu

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Marketplace Gading Kirana", layout="wide")

# --- INISIALISASI SESSION STATE (BAGIAN YANG DIPERBAIKI) ---
if 'cart' not in st.session_state:
    st.session_state.cart = [] # Memberikan nilai daftar kosong
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
# CSS custom
st.markdown("""
    <style>
        html, body, [class*="css"] {
            background-color: #2c3e50;
            color: #ecf0f1;
            font-family: 'Segoe UI', sans-serif;
        }
        .main-header {
            font-size: 2.5em;
            font-weight: bold;
            color: #f39c12;
            padding-bottom: 0.2em;
        }
        .sub-header {
            font-size: 1.2em;
            color: #bdc3c7;
            margin-bottom: 1em;
        }
        .highlight {
            color: #ffffff;
            background-color: #e67e22;
            padding: 0.3em 0.6em;
            border-radius: 6px;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# Layout: 2 kolom
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown('<div class="main-header">Marketplace Gading Kirana</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Temukan produk terbaik dari <span class="highlight">tetangga Anda</span> dan dukung ekonomi lokal!</div>', unsafe_allow_html=True)

with col2:
    st.image("https://borneoshops.com/image/marketplace/storeicon.png", width=200)

st.markdown("""<hr style="border-top: 1px solid #7f8c8d;">""", unsafe_allow_html=True)
# --- NAVIGASI ---
with st.sidebar:
    menu_selection = option_menu(
        "📍 Navigasi",
        ["Belanja", "Keranjang", "Portal Penjual", "Daftar sebagai Penjual"],
        icons=["shop", "cart", "shop-window", "person-plus"],
        default_index=0,
        styles={
            "container": {
                "padding": "10px",
                "background-color": "#2c3e50",  # background gelap
            },
            "icon": {
                "color": "#f1c40f",  # kuning terang
                "font-size": "20px"
            },
            "nav-link": {
                "font-size": "16px",
                "text-align": "left",
                "color": "#ecf0f1",  # teks putih
                "--hover-color": "#34495e"
            },
            "nav-link-selected": {
                "background-color": "#f39c12",
                "color": "white",
                "font-weight": "bold"
            },
        }
    )
# =================================================================
# --- HALAMAN BELANJA ---
# =================================================================
if menu_selection == "Belanja":
    st.markdown("### 🛍️ Katalog Produk")
    st.markdown("_Temukan produk terbaik dari tetangga Anda!_")

    # Ambil data produk dan penjual
    products_df = get_data("Products")
    vendors_df = get_data("Vendors")

    # Preprocessing
    products_df['is_active'] = products_df['is_active'].apply(lambda x: str(x).lower() == 'true')
    products_df = pd.merge(products_df, vendors_df[['vendor_id', 'vendor_name']], on='vendor_id', how='left')

    # Sidebar: Filter
    st.sidebar.header("🔍 Filter Pencarian")
    vendor_list = vendors_df['vendor_name'].dropna().unique().tolist()
    selected_vendor = st.sidebar.selectbox("Pilih Penjual", ["Semua"] + vendor_list)
    search_query = st.sidebar.text_input("Cari Nama Produk")

    # Filter Produk Aktif
    active_products = products_df[products_df['is_active'] == True]

    if selected_vendor != "Semua":
        active_products = active_products[active_products['vendor_name'] == selected_vendor]

    if search_query:
        active_products = active_products[active_products['product_name'].str.contains(search_query, case=False)]

    # Tampilkan
    if active_products.empty:
        st.warning("🚫 Tidak ada produk yang sesuai dengan filter.")
    else:
        st.markdown("---")
        cols = st.columns(3)  # 3 produk per baris

        for index, product in active_products.iterrows():
            col = cols[index % 3]
            with col:
                with st.container(border=True):
                    # Gambar produk (ukuran konsisten)
                    image_url = product.get('image_url', '').strip()
                    img_src = image_url if image_url else "https://via.placeholder.com/200"
                    st.image(img_src, width=200)

                    # Info produk
                    st.markdown(f"**{product['product_name'][:30]}**")
                    st.caption(f"🧑 {product['vendor_name']}")
                    st.markdown(f"💰 Rp {int(product['price']):,}")
                    st.caption(product['description'][:60] + "..." if len(product['description']) > 60 else product['description'])

                    # Tombol beli
                    if st.button("➕ Tambah ke Keranjang", key=f"add_{product['product_id']}"):
                        add_to_cart(product)

# =================================================================
# --- HALAMAN KERANJANG BELANJA ---
# =================================================================
elif menu_selection == "Keranjang":
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
                                #vendor_info = vendors_df[vendors_df['vendor_id'] == vendor_id].iloc
                                items_from_vendor = [f"{item['quantity']}x {item['product_name']}" for item in st.session_state.cart if item['vendor_id'] == vendor_id]
                                vendor_info = vendors_df[vendors_df['vendor_id'] == vendor_id]
                                if not vendor_info.empty:
                                    vendor_info = vendor_info.iloc[0]
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

                            # Mengosongkan keranjang setelah berhasil (BAGIAN YANG DIPERBAIKI)
                            st.session_state.cart = []

# =================================================================
# --- HALAMAN PORTAL PENJUAL ---
# =================================================================
elif menu_selection == "Portal Penjual":
    if not st.session_state.get('logged_in'):
        login_form()
        st.stop()
    else:
        st.sidebar.success(f"Login sebagai: **{st.session_state.get('vendor_name', 'Guest')}**")
        logout()

    vendor_id = st.session_state.get('vendor_id')
    if not vendor_id:
        st.error("Vendor ID tidak ditemukan.")
        st.stop()

    st.header(f"Dashboard: {st.session_state['vendor_name']}")
    st.subheader("📦 Produk Anda")

    try:
        # Ambil data produk vendor
        products_df = get_data("Products")
        my_products = products_df[products_df['vendor_id'] == vendor_id]

        # ------------------ FILTER ------------------
        filter_status = st.selectbox("Filter Produk:", ["Semua", "Aktif", "Nonaktif"])
        if filter_status == "Aktif":
            my_products = my_products[my_products['is_active'] == True]
        elif filter_status == "Nonaktif":
            my_products = my_products[my_products['is_active'] == False]

        if my_products.empty:
            st.info("Anda belum memiliki produk.")
        else:
            st.dataframe(my_products)

        # ------------------ HAPUS PRODUK ------------------
        with st.expander("🗑️ Hapus Produk"):
            delete_id = st.selectbox("Pilih Produk yang Ingin Dihapus", my_products['product_id'].tolist())
            if st.button("Hapus Produk Ini"):
                products_ws = get_worksheet("Products")
                if products_ws:
                    cell = products_ws.find(delete_id)
                    if cell:
                        products_ws.delete_rows(cell.row)
                        st.success(f"Produk dengan ID {delete_id} berhasil dihapus.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Produk tidak ditemukan.")

    except Exception as e:
        st.error("Gagal memuat data produk.")
        st.write(e)

    # ------------------ TAMBAH / EDIT PRODUK ------------------
        with st.expander("➕ Tambah atau Edit Produk"):
            try:
                products_df = get_data("Products")
                my_products = products_df[products_df['vendor_id'] == vendor_id]
                existing_ids = my_products['product_id'].tolist()

        # --- Langkah 1: Pilih Produk di luar Form
                selected_product_id = st.selectbox(
            "Pilih Produk untuk Diedit (kosongkan jika ingin tambah produk baru)",
                    [""] + existing_ids,
                    key="selected_product_id"
                )

        # --- Langkah 2: Ambil Data Produk Jika Ada
                if selected_product_id:
                    product_data = my_products[my_products['product_id'] == selected_product_id].iloc[0]
                    default_name = product_data['product_name']
                    default_desc = product_data['description']
                    default_price = int(product_data['price'])
                    default_stock = int(product_data['stock_quantity'])
                    default_active = product_data['is_active']
                    default_image = product_data['image_url']
                else:
                    default_name = ""
                    default_desc = ""
                    default_price = 0
                    default_stock = 0
                    default_active = True
                    default_image = ""

        # --- Langkah 3: Tampilkan Form
                with st.form("product_form", clear_on_submit=True):
                    product_name = st.text_input("Nama Produk", value=default_name)
                    description = st.text_area("Deskripsi", value=default_desc)
                    price = st.number_input("Harga", min_value=0, value=default_price)
                    stock_quantity = st.number_input("Jumlah Stok", min_value=0, value=default_stock)
                    is_active = st.checkbox("Tampilkan Produk?", value=default_active)

                    if default_image:
                        st.image(default_image, width=200, caption="Gambar Produk Saat Ini")

                    uploaded_file = st.file_uploader("Upload Gambar Baru (opsional)", type=["jpg", "jpeg", "png"])
                    image_url = default_image

                    submitted = st.form_submit_button("💾 Simpan Produk")

                    if submitted:
                        if not product_name or not description:
                            st.warning("Nama produk dan deskripsi wajib diisi.")
                            st.stop()

                        products_ws = get_worksheet("Products")

                        if uploaded_file:
                            os.makedirs("images", exist_ok=True)
                            image_url = f"images/{uuid.uuid4().hex[:8]}.jpg"
                            with open(image_url, "wb") as f:
                                f.write(uploaded_file.read())
                            st.image(image_url, width=200, caption="Gambar Baru")

                        product_id = selected_product_id if selected_product_id else f"PROD-{uuid.uuid4().hex[:6].upper()}"
                        new_row = [
                            product_id, vendor_id, product_name, description, price,
                            image_url, stock_quantity, is_active,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ]

                        if selected_product_id:
                    # Update produk
                            cell = products_ws.find(selected_product_id)
                            if cell:
                                products_ws.update(f"A{cell.row}:I{cell.row}", [new_row])
                                st.success(f"Produk '{product_name}' berhasil diperbarui!")
                            else:
                                st.error("Produk tidak ditemukan.")
                        else:
                    # Tambah produk baru
                            products_ws.append_row(new_row)
                            st.success(f"Produk baru '{product_name}' berhasil ditambahkan!")

                        st.cache_data.clear()
                        st.rerun()

            except Exception as e:
                st.error("Gagal menampilkan form produk.")
                st.write(e)

# =================================================================
# --- HALAMAN PENDAFTARAN VENDOR ---
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
            if not all([vendor_name, username, whatsapp_number, password, confirm_password]):
                st.warning("Semua kolom wajib diisi.")
            elif password!= confirm_password:
                st.error("Password dan konfirmasi password tidak cocok.")
            else:
                with st.spinner("Mendaftarkan akun Anda..."):
                    vendors_df = get_data("Vendors")
                    
                    if not vendors_df.empty and username in vendors_df['username'].values:
                        st.error("Username ini sudah digunakan. Silakan pilih yang lain.")
                    else:
                        vendors_ws = get_worksheet("Vendors")
                        if vendors_ws:
                            vendor_id = f"VEND-{uuid.uuid4().hex[:6].upper()}"
                            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                            
                            new_vendor_row = [vendor_id, vendor_name, username, hashed_password, whatsapp_number]
                            
                            vendors_ws.append_row(new_vendor_row)
                            
                            st.success(f"Pendaftaran berhasil! Selamat datang, {vendor_name}. Silakan login melalui 'Portal Penjual'.")
                            st.balloons()
                            
                            st.cache_data.clear()
                        else:
                            st.error("Gagal terhubung ke database. Coba lagi nanti.")
