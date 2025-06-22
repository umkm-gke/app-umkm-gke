import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
import json
from urllib.parse import quote_plus
import bcrypt # Diperlukan untuk hashing password pendaftaran
import os
import io

from g_sheets import get_data, get_worksheet
from auth import login_form, logout

from streamlit_option_menu import option_menu

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
    jakarta_tz = ZoneInfo("Asia/Jakarta")
except ImportError:
    import pytz
    jakarta_tz = pytz.timezone("Asia/Jakarta")

def now_jakarta():
    return datetime.now(jakarta_tz)

def format_jakarta(dt, fmt="%Y-%m-%d %H:%M:%S"):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=jakarta_tz)
    else:
        dt = dt.astimezone(jakarta_tz)
    return dt.strftime(fmt)
    
# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Marketplace Gading Kirana", layout="wide")

# --- INISIALISASI SESSION STATE (BAGIAN YANG DIPERBAIKI) ---
if 'role' not in st.session_state:
    st.session_state['role'] = 'guest'
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

role = st.session_state['role']
def set_role_after_login():
    if st.session_state.get('logged_in'):
        if st.session_state.get('is_admin', False):
            st.session_state['role'] = 'admin'
        else:
            st.session_state['role'] = 'vendor'
    else:
        st.session_state['role'] = 'guest'

set_role_after_login()

# --- FUNGSI BANTU ---
def add_to_cart(product: dict) -> None:
    """
    Menambahkan produk ke keranjang belanja di session state.

    Jika produk sudah ada di keranjang, jumlahnya ditambah 1.
    Jika belum ada, produk baru ditambahkan dengan quantity 1.

    Args:
        product (dict): Data produk dengan setidaknya keys
            'product_id', 'product_name', 'price', dan 'vendor_id'.
    """
    # Inisialisasi keranjang jika belum ada
    if 'cart' not in st.session_state:
        st.session_state.cart = []

    # Cek apakah produk sudah ada di keranjang
    for item in st.session_state.cart:
        if item['product_id'] == product['product_id']:
            item['quantity'] += 1
            st.toast(f"Jumlah {product['product_name']} ditambah!", icon="🛒")
            return

    # Produk baru, tambahkan ke keranjang
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

def reset_password_vendor():
    st.header("🔒 Reset Password Vendor")

    username = st.text_input("Masukkan Username Anda")

    if username:
        vendors_df = get_data("Vendors")
        vendor_data = vendors_df[vendors_df['username'] == username]

        if vendor_data.empty:
            st.error("Username tidak ditemukan.")
            return

        new_password = st.text_input("Password Baru", type="password")
        confirm_password = st.text_input("Konfirmasi Password Baru", type="password")

        if st.button("Reset Password"):
            if not new_password or not confirm_password:
                st.warning("Password dan konfirmasi harus diisi.")
            elif new_password != confirm_password:
                st.warning("Password dan konfirmasi tidak sama.")
            else:
                hashed_new_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                vendors_ws = get_worksheet("Vendors")
                cell = vendors_ws.find(username)
                if cell:
                    password_col_index = vendors_df.columns.get_loc('password_hash') + 1
                    vendors_ws.update_cell(cell.row, password_col_index, hashed_new_pw)
                    st.success("Password berhasil direset. Silakan login dengan password baru.")
                else:
                    st.error("Gagal menemukan akun di database.")

# --- NAVIGASI ---
with st.sidebar:

    role = st.session_state.get("role", "guest")
    
    # Ambil data vendor untuk cek jumlah pending (untuk admin)
    vendors_df = get_data("Vendors") if role != 'admin' else pd.DataFrame()
    jumlah_pending = 0
    if not vendors_df.empty:
        jumlah_pending = vendors_df[vendors_df['status'].str.lower() == 'pending'].shape[0]

    # Menu sesuai role
    if role == 'admin':
        menu_items = [f"Verifikasi Pendaftar ({jumlah_pending})" if jumlah_pending > 0 else "Verifikasi Pendaftar"]
        icons = ["shield-lock"]
    elif role == 'vendor':
        menu_items = ["Portal Penjual"]
        icons = ["box-seam"]
    else:
        menu_items = ["Belanja", "Keranjang", "Daftar sebagai Penjual", "Reset Password"]
        icons = ["shop", "cart", "person-plus"]

    # TAMPILAN NAVIGASI
    menu_selection = option_menu(
        "📍 Navigasi",
        menu_items,
        icons=icons,
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
    if menu_selection == "Reset Password":
        reset_password_vendor()
# =================================================================
# --- HALAMAN PEMBELI (Guest) ---
# =================================================================
if role == 'guest':
    if menu_selection == "Belanja":
        st.markdown("### 🛍️ Katalog Produk")
        st.markdown("_Temukan produk terbaik dari tetangga Anda!_")

        # Ambil data produk dan penjual
        products_df = get_data("Products")
        if 'category' not in products_df.columns:
            products_df['category'] = ""

        vendors_df = get_data("Vendors")

        # Pastikan kolom is_active di products_df menjadi boolean (true jika 'true' string, else false)
        products_df['is_active'] = products_df['is_active'].apply(lambda x: str(x).lower() == 'true')

        # Pastikan kolom is_active di vendors_df juga boolean
        vendors_df['is_active'] = vendors_df['is_active'].apply(lambda x: str(x).lower() == 'true')

        # Merge produk dengan vendor untuk dapatkan nama vendor dan status aktif vendor
        products_df = pd.merge(
            products_df,
            vendors_df[['vendor_id', 'vendor_name', 'is_active']],
            on='vendor_id',
            how='left',
            suffixes=('', '_vendor')
        )

        # Sidebar: Filter
        st.sidebar.header("🔍 Filter Pencarian")

        # Daftar vendor aktif untuk dropdown
        active_vendors_df = vendors_df[vendors_df['is_active'] == True]
        vendor_list = active_vendors_df['vendor_name'].dropna().unique().tolist()
        selected_vendor = st.sidebar.selectbox("Pilih Penjual", ["Semua"] + vendor_list)

        # Filter kategori berdasar produk yang aktif dan vendor aktif juga
        # Jadi kita gunakan produk yang vendor-nya aktif dan produk itu aktif
        active_products = products_df[
            (products_df['is_active'] == True) &
            (products_df['is_active_vendor'] == True)
        ]

        kategori_list = sorted(active_products['category'].dropna().unique().tolist())
        selected_kategori = st.sidebar.selectbox("Kategori", ["Semua"] + kategori_list)

        search_query = st.sidebar.text_input("Cari Nama Produk")

        # Terapkan filter kategori
        if selected_kategori != "Semua":
            active_products = active_products[active_products['category'] == selected_kategori]

        # Terapkan filter vendor
        if selected_vendor != "Semua":
            active_products = active_products[active_products['vendor_name'] == selected_vendor]

        # Terapkan filter pencarian nama produk
        if search_query:
            active_products = active_products[
                active_products['product_name'].str.contains(search_query, case=False, na=False)
            ]

        # Tampilkan hasil filter
        if active_products.empty:
            st.warning("🚫 Tidak ada produk yang sesuai dengan filter.")
        else:
            st.markdown("---")
            cols = st.columns(4)  # 3 produk per baris

            for index, product in active_products.iterrows():
                col = cols[index % 4]
                with col:
                    with st.container():
                        # Gambar produk (ukuran konsisten)
                        image_url = product.get('image_url', '').strip()
                        img_src = image_url if image_url else "https://via.placeholder.com/200"
                        st.image(img_src, width=160)

                        # Info produk
                        st.markdown(f"**{product['product_name'][:30]}**")
                        st.caption(f"Kategori: {product.get('category', 'Tidak tersedia')}")
                        st.caption(f"🧑 {product['vendor_name']}")
                        st.markdown(f"💰 Rp {int(product['price']):,}")
                        description = product.get('description', '')
                        st.caption(description[:60] + "..." if len(description) > 60 else description)

                        # Tombol beli
                        if st.button("➕ Tambah ke Keranjang", key=f"add_{product['product_id']}"):
                            add_to_cart(product)

    if 'cart' not in st.session_state:
        st.session_state.cart = []
    elif menu_selection == "Keranjang":
        st.header("🛒 Keranjang Belanja Anda")
        cart = st.session_state.get("cart", [])
    
        if not cart:
            st.info("Keranjang Anda masih kosong. Yuk, mulai belanja!")
            return
    
        total_price = 0
        vendors_in_cart = {}
    
        # Tampilkan isi keranjang
        for i, item in enumerate(cart):
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    st.subheader(item['product_name'])
                    st.write(f"Rp {item['price']:,}")
                with col2:
                    new_quantity = st.number_input("Jumlah", min_value=1, value=item['quantity'], key=f"qty_{i}")
                    cart[i]['quantity'] = new_quantity
                with col3:
                    subtotal = item['price'] * item['quantity']
                    st.metric("Subtotal", f"Rp {subtotal:,}")
                with col4:
                    if st.button("Hapus", key=f"del_{i}"):
                        cart.pop(i)
                        st.session_state.cart = cart
                        st.rerun()
    
            total_price += item['price'] * item['quantity']
            vendor_id = item['vendor_id']
            vendors_in_cart[vendor_id] = vendors_in_cart.get(vendor_id, 0) + subtotal
    
        st.session_state.cart = cart  # update after quantity change
        st.header(f"Total Belanja: Rp {total_price:,}")
    
        # Metode pembayaran global (satu untuk semua vendor)
        st.subheader("🧾 Pilih Metode Pembayaran")
        payment_method = st.radio("Metode Pembayaran", ["Tunai", "Transfer Bank", "QRIS"], index=1, horizontal=True)
    
        # Form Checkout
        st.subheader("📝 Lanjutkan Pemesanan")
        with st.form("checkout_form"):
            customer_name = st.text_input("Nama Anda")
            customer_contact = st.text_input("Nomor HP Anda (untuk konfirmasi)")
            submit_order = st.form_submit_button("Buat Pesanan Sekarang")
    
            if submit_order:
                if not customer_name or not customer_contact:
                    st.warning("Nama dan Nomor HP tidak boleh kosong.")
                    return
    
                with st.spinner("Memproses pesanan..."):
                    orders_ws = get_worksheet("Orders")
                    vendors_df = get_data("Vendors")
    
                    if orders_ws is None or vendors_df.empty:
                        st.error("Gagal memproses pesanan. Coba lagi.")
                        return
    
                    order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
                    order_details_json = json.dumps(cart)
                    timestamp = format_jakarta(now_jakarta())
                    orders_ws.append_row([
                        order_id, customer_name, customer_contact,
                        order_details_json, total_price, "Baru", timestamp
                    ])
    
                    st.success(f"Pesanan Anda ({order_id}) berhasil dibuat!")
                    st.balloons()
    
                    st.subheader("Rincian Tagihan & Konfirmasi Pesanan")
                    st.info("Silakan lakukan pembayaran ke masing-masing penjual dan konfirmasi pesanan.")
    
                    for vendor_id, amount in vendors_in_cart.items():
                        vendor_info_df = vendors_df[vendors_df['vendor_id'] == vendor_id]
                        if vendor_info_df.empty:
                            continue
    
                        vendor_info = vendor_info_df.iloc[0]
                        items = [f"{item['quantity']}x {item['product_name']}" for item in cart if item['vendor_id'] == vendor_id]
                        payment_info = ""
    
                        st.write("---")
                        st.write(f"**Penjual: {vendor_info['vendor_name']}**")
                        st.write(f"**Total Tagihan: Rp {amount:,}**")
    
                        if payment_method == "Transfer Bank":
                            bank_info = vendor_info.get("bank_account", "")
                            st.write(f"**Transfer ke Rekening:** {bank_info or 'Belum tersedia'}")
                            payment_info = f"Metode: Transfer Bank\nRekening: {bank_info}"
    
                        elif payment_method == "QRIS":
                            qris_url = vendor_info.get("qris_url", "")
                            if isinstance(qris_url, str) and qris_url.lower().startswith("http") and qris_url.lower().endswith(('.jpg', '.jpeg', '.png')):
                                st.image(qris_url, caption="Atau scan QRIS", width=250)
                                payment_info = "Metode: QRIS (lihat gambar)"
                            else:
                                st.warning("QRIS belum tersedia.")
                                payment_info = "Metode: QRIS (belum tersedia)"
    
                        else:
                            st.info("Pembayaran dilakukan saat barang diterima.")
                            payment_info = "Metode: Tunai saat barang diterima"
    
                        message = (
                            f"Halo {vendor_info['vendor_name']}, saya {customer_name} ingin konfirmasi pesanan {order_id}.\n\n"
                            f"Pesanan saya:\n{', '.join(items)}\n\n"
                            f"Total: Rp {amount:,}\n"
                            f"{payment_info}\n\nTerima kasih!"
                        )
    
                        encoded_message = quote_plus(message)
                        whatsapp_url = f"https://wa.me/{vendor_info['whatsapp_number']}?text={encoded_message}"
                        st.link_button(f"💬 Konfirmasi ke {vendor_info['vendor_name']} via WhatsApp", whatsapp_url)
    
                    # Kosongkan keranjang setelah selesai
                    st.session_state.cart = []


    elif menu_selection == "Daftar sebagai Penjual":
        st.header("✍️ Pendaftaran Penjual Baru")
        st.write("Isi formulir di bawah ini untuk mulai berjualan di platform kami.")
    
        with st.form("vendor_registration_form", clear_on_submit=True):
            st.subheader("📝 Formulir Pendaftaran Penjual")
            st.caption("Silakan isi data di bawah ini untuk mulai berjualan di platform kami.")
        
            vendor_name = st.text_input("Nama Toko / UMKM Anda")
            username = st.text_input("Username (untuk login)")
            whatsapp_number = st.text_input("Nomor WhatsApp (format: 628xxxxxxxxxx)")
        
            # ✅ Input Transfer Bank (WAJIB)
            bank_account = st.text_input(
                "Info Rekening Bank (WAJIB)",
                placeholder="Contoh: BCA - 1234567890 a.n. Toko ABC"
            )
        
            # ✅ Input QRIS (OPSIONAL) + Validasi
            qris_url = st.text_input(
                "Link Gambar QRIS (Opsional)",
                placeholder="Contoh: https://i.imgur.com/namafile.png"
            )
        
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Konfirmasi Password", type="password")
        
            submitted = st.form_submit_button("Daftar Sekarang")
        
            # ==== VALIDASI ====
            def is_valid_image_url(url):
                valid_extensions = [".jpg", ".jpeg", ".png"]
                return url.lower().startswith("http") and any(url.lower().endswith(ext) for ext in valid_extensions)
        
            if submitted:
                if not all([vendor_name, username, whatsapp_number, bank_account, password, confirm_password]):
                    st.warning("Semua kolom wajib diisi, kecuali QRIS.")
                elif password != confirm_password:
                    st.error("Password dan konfirmasi password tidak cocok.")
                elif qris_url and not is_valid_image_url(qris_url):
                    st.error("Link QRIS harus berupa URL gambar dengan format .jpg, .jpeg, atau .png.")
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
        
                                new_vendor_row = [
                                    vendor_id,
                                    vendor_name,
                                    username,
                                    hashed_password,
                                    whatsapp_number,
                                    "pending",      # status
                                    "false",        # default saat daftar
                                    bank_account,
                                    qris_url or ""  # jika kosong, isi dengan string kosong
                                ]
        
                                vendors_ws.append_row(new_vendor_row)
        
                                st.success(
                                    f"Pendaftaran berhasil, {vendor_name}! "
                                    "Akun Anda sedang menunggu persetujuan admin. "
                                    "Kami akan menghubungi Anda setelah disetujui."
                                )
                                st.balloons()
                                st.cache_data.clear()
                            else:
                                st.error("Gagal terhubung ke database. Coba lagi nanti.")
        
            # Bantuan untuk vendor gaptek
            st.info("Jika kesulitan mengunggah QRIS, Anda dapat mengirimkannya ke Admin melalui WhatsApp: 62812XXXXXXX")

    with st.sidebar:
            st.markdown("### 🔐 Login Vendor / Admin")
            login_form()

# =================================================================
# --- HALAMAN PORTAL PENJUAL ---
# =================================================================
elif role == 'vendor':
    if menu_selection == "Portal Penjual":
        if not st.session_state.get('logged_in') or st.session_state.get('is_admin', False):
            st.warning("Silakan login sebagai vendor untuk mengakses Portal Penjual.")
            login_form()
            st.stop()
        else:
            st.sidebar.success(f"Login sebagai: **{st.session_state.get('vendor_name', 'Guest')}**")
            logout()
        vendor_id = st.session_state.get('vendor_id')
        if not vendor_id and not st.session_state.get('is_admin', False):
            st.error("Vendor ID tidak ditemukan.")
            st.stop()
    
    
        st.header(f"Dashboard: {st.session_state['vendor_name']}")
        # ------------------ DAFTAR PESANAN MASUK ------------------
        with st.expander("📋 Daftar Pesanan Masuk"):
            try:
                orders_df = get_data("Orders")
        
                # Parsing kolom timestamp ke datetime
                orders_df['timestamp'] = pd.to_datetime(orders_df['timestamp'], errors='coerce')
                orders_df['timestamp'] = orders_df['timestamp'].dt.tz_localize("UTC").dt.tz_convert(jakarta_tz)
                
                # Definisikan rentang waktu maksimal data yang bisa di-load
                today = now_jakarta()
                three_months_ago = today - pd.DateOffset(months=3)
        
                # Filter data 3 bulan terakhir saja
                orders_df = orders_df[orders_df['timestamp'] >= three_months_ago]
        
                vendor_id = st.session_state.get("vendor_id")
        
                relevant_orders = []
        
                for _, row in orders_df.iterrows():
                    try:
                        items = json.loads(row['order_details'])
                        for item in items:
                            if item.get('vendor_id') == vendor_id:
                                relevant_orders.append({
                                    "order_id": row['order_id'],
                                    "product_name": item.get('product_name'),
                                    "quantity": item.get('quantity'),
                                    "price": item.get('price'),
                                    "total_item_price": item.get('price') * item.get('quantity'),
                                    "customer_name": row['customer_name'],
                                    "contact": row['customer_contact'],
                                    "status": row['order_status'],
                                    "timestamp": row['timestamp']
                                })
                    except Exception as e:
                        st.warning(f"⛔ Pesanan {row['order_id']} tidak bisa diproses: {e}")
        
                if not relevant_orders:
                    st.info("Belum ada pesanan yang masuk untuk Anda.")
                else:
                    orders_display_df = pd.DataFrame(relevant_orders)
        
                    # Filter tanggal wajib dipilih, dengan rentang 3 bulan terakhir
                    selected_date_range = st.date_input(
                        "📆 Filter Rentang Tanggal Pesanan",
                        value=(today.date(), today.date()),
                        min_value=three_months_ago.date(),
                        max_value=today.date()
                    )
                    
                    # Validasi range input
                    if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
                        start_date, end_date = selected_date_range
                        orders_display_df = orders_display_df[
                            (orders_display_df['timestamp'].dt.date >= start_date) &
                            (orders_display_df['timestamp'].dt.date <= end_date)
                        ]
        
                    # Filter status dengan pilihan "Semua"
                    filter_status = st.selectbox(
                        "Filter Status Pesanan",
                        ["Semua", "Baru", "Diproses", "Selesai", "Dibatalkan"]
                    )
                    if filter_status != "Semua":
                        orders_display_df = orders_display_df[orders_display_df['status'] == filter_status]
        
                    # Batasi jumlah data maksimal tampil jika checkbox tidak dicentang
                    MAX_ORDERS_DISPLAY = 50
                    #if not show_all:
                    orders_display_df = orders_display_df.sort_values(by='timestamp', ascending=False).head(MAX_ORDERS_DISPLAY)
                    #else:
                        #orders_display_df = orders_display_df.sort_values(by='timestamp', ascending=False)
        
                    if orders_display_df.empty:
                        st.info("Tidak ada pesanan yang sesuai dengan filter.")
                    else:
                        st.dataframe(
                            orders_display_df[
                                ["timestamp", "order_id", "product_name", "quantity", "total_item_price", "customer_name", "status"]
                            ],
                            use_container_width=False
                        )
        
                        # Ubah status (optional)
                        selected_order_id = st.selectbox(
                            "Pilih Pesanan untuk Perubahan Status",
                            orders_display_df['order_id'].unique()
                        )
                        new_status = st.selectbox("Status Baru", ["Baru", "Diproses", "Selesai", "Dibatalkan"])
                        if st.button("✅ Perbarui Status Pesanan"):
                            orders_ws = get_worksheet("Orders")
                            if orders_ws:
                                cell = orders_ws.find(selected_order_id)
                                if cell:
                                    # Misal kolom order_status di kolom F
                                    orders_ws.update(f"F{cell.row}", [[new_status]])
                                    st.success(f"Status pesanan `{selected_order_id}` berhasil diubah ke **{new_status}**.")
                                    st.cache_data.clear()
                                    #st.rerun()
                                else:
                                    st.error("Tidak dapat menemukan pesanan.")
            except Exception as e:
                st.error("Gagal memuat daftar pesanan.")
                st.write(e)
   
#========================================================================================
        with st.expander("📦 Produk Anda"):
    
            try:
                # Ambil data produk milik vendor
                products_df = get_data("Products")
                if 'category' not in products_df.columns:
                    products_df['category'] = ""
                my_products = products_df[products_df['vendor_id'] == vendor_id]
        
                # ------------------ FILTER PRODUK ------------------
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
                    if not my_products.empty:
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
                    else:
                        st.caption("Belum ada produk yang bisa dihapus.")
        
            except Exception as e:
                st.error("Gagal memuat data produk.")
                st.write(e)
        
            # ------------------ TAMBAH / EDIT PRODUK ------------------
            with st.expander("➕ Tambah atau Edit Produk"):
                try:
                    products_df = get_data("Products")
                    if 'category' not in products_df.columns:
                        products_df['category'] = ""
                    my_products = products_df[products_df['vendor_id'] == vendor_id]
                    existing_ids = my_products['product_id'].tolist()
        
                    # Pilihan produk di luar form
                    selected_product_id = st.selectbox(
                        "Pilih Produk untuk Diedit (kosongkan jika ingin tambah produk baru)",
                        [""] + existing_ids,
                        key="selected_product_id"
                    )
        
                    # Ambil data produk jika ada
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
        
                    # Form input
                    with st.form("product_form", clear_on_submit=True):
                        product_name = st.text_input("Nama Produk", value=default_name)
                        description = st.text_area("Deskripsi", value=default_desc)
                        price = st.number_input("Harga", min_value=0, value=default_price)
                        stock_quantity = st.number_input("Jumlah Stok", min_value=0, value=default_stock)
                        is_active = st.checkbox("Tampilkan Produk?", value=default_active)
                        kategori_list = ["Makanan", "Minuman", "Rumah Tangga", "Kesehatan", "Bayi", "Mainan", "Lainnya"]
                        kategori = st.selectbox("Kategori Produk", options=kategori_list, index=0 if not selected_product_id else kategori_list.index(product_data['category']) if product_data['category'] in kategori_list else len(kategori_list)-1)
        
        
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
        
                            # Simpan gambar baru jika diupload
                            if uploaded_file:
                                os.makedirs("images", exist_ok=True)
                                image_url = f"images/{uuid.uuid4().hex[:8]}.jpg"
                                with open(image_url, "wb") as f:
                                    f.write(uploaded_file.read())
                                st.image(image_url, width=200, caption="Gambar Baru")
        
                            product_id = selected_product_id if selected_product_id else f"PROD-{uuid.uuid4().hex[:6].upper()}"
                            # Convert is_active to string explicitly
                            is_active_str = "true" if is_active else "false"
                            new_row = [
                                product_id, vendor_id, product_name, description, price,
                                image_url, stock_quantity, is_active_str, kategori,
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ]

                            if selected_product_id:
                                # Update produk
                                cell = products_ws.find(selected_product_id)
                                if cell:
                                    products_ws.update(f"A{cell.row}:J{cell.row}", [new_row])
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

 # ------------------ UPDATE DATA VENDOR ------------------
    
        with st.expander("✏️ Update Data Toko"):
            def is_valid_image_url(url: str) -> bool:
                return url.lower().startswith("http") and url.lower().endswith((".jpg", ".jpeg", ".png"))
            
            try:
                vendor_id = st.session_state.vendor_id
                vendors_df = get_data("Vendors")
                vendors_ws = get_worksheet("Vendors")
        
                vendor_info = vendors_df[vendors_df['vendor_id'] == vendor_id].iloc[0]
        
                updated_bank = st.text_input("Info Rekening Bank", value=vendor_info.get("bank_account", ""))
                updated_qris = st.text_input(
                    "Link Gambar QRIS",
                    value=vendor_info.get("qris_url", ""),
                    placeholder="https://i.imgur.com/qriscontoh.png"
                )
        
                if st.button("💾 Simpan Perubahan"):
                    if updated_qris and not is_valid_image_url(updated_qris):
                        st.error("Link QRIS harus berupa URL gambar dengan ekstensi .jpg, .jpeg, atau .png")
                    else:
                        try:
                            cell = vendors_ws.find(vendor_id)
                            row = cell.row
        
                            # Update kolom bank_account dan qris_url (pastikan kolom sesuai dengan struktur GSheet Anda)
                            vendors_ws.update_cell(row, 8, updated_bank)  # kolom H
                            vendors_ws.update_cell(row, 9, updated_qris)  # kolom I
        
                            st.success("Data berhasil diperbarui.")
                            #st.experimental_rerun()
                        except Exception as e:
                            st.error("Gagal memperbarui data.")
                            st.write(e)
        
            except Exception as e:
                st.error("Gagal memuat data vendor.")
                st.write(e)

 # ------------------ LAPORAN KEUANGAN VENDOR ------------------
        with st.expander("💰 Laporan Keuangan"):
            try:
                orders_df = get_data("Orders")
                vendor_id = st.session_state.get("vendor_id")
        
                import json
                transactions = []
        
                # Ambil semua transaksi selesai dari vendor
                for _, row in orders_df.iterrows():
                    if row['order_status'] == "Selesai":
                        try:
                            items = json.loads(row['order_details'])
                            for item in items:
                                if item.get('vendor_id') == vendor_id:
                                    transactions.append({
                                        "order_id": row['order_id'],
                                        "product_name": item.get("product_name"),
                                        "quantity": item.get("quantity"),
                                        "price": item.get("price"),
                                        "total": item.get("price") * item.get("quantity"),
                                        "timestamp": row["timestamp"],
                                        "customer_name": row.get("customer_name", ""),
                                        "customer_contact": row.get("customer_contact", "")
                                    })
                        except Exception as e:
                            st.warning(f"Transaksi tidak valid: {e}")
        
                if not transactions:
                    st.info("Belum ada transaksi selesai yang masuk.")
                else:
                    df_financial = pd.DataFrame(transactions)
                    df_financial['timestamp'] = pd.to_datetime(df_financial['timestamp'])
        
                    # Filter tanggal
                    min_date = df_financial['timestamp'].min().date()
                    max_date = df_financial['timestamp'].max().date()
                    date_range = st.date_input(
                        "Filter Tanggal Transaksi",
                        value=(min_date, max_date),
                        min_value=min_date,
                        max_value=max_date
                    )
        
                    if len(date_range) == 2:
                        start_date, end_date = date_range
                        df_financial = df_financial[(df_financial['timestamp'].dt.date >= start_date) &
                                                    (df_financial['timestamp'].dt.date <= end_date)]
        
                    # Filter produk
                    produk_list = df_financial['product_name'].unique().tolist()
                    produk_pilih = st.selectbox("Filter berdasarkan produk:", ["Semua"] + produk_list)
        
                    if produk_pilih != "Semua":
                        df_financial = df_financial[df_financial['product_name'] == produk_pilih]
        
                    # Tampilkan total pendapatan
                    total_income = df_financial['total'].sum()
                    st.metric("💵 Total Pendapatan", f"Rp {total_income:,.0f}")
        
                    if not df_financial.empty:
                        # Tabel detail transaksi
                        with st.expander("📄 Detail Transaksi"):
                            df_display = df_financial.sort_values(by="timestamp", ascending=False)[
                                ["timestamp", "order_id", "customer_name", "customer_contact", "product_name", "quantity", "price", "total"]
                            ].rename(columns={
                                "timestamp": "Tanggal & Waktu",
                                "order_id": "ID Pesanan",
                                "customer_name": "Nama Pembeli",
                                "customer_contact": "Kontak Pembeli",
                                "product_name": "Nama Produk",
                                "quantity": "Jumlah",
                                "price": "Harga Satuan",
                                "total": "Total"
                            })
                        
                            st.dataframe(df_display, use_container_width=False)

                        
                        # Download Excel
                        
                        df_to_save = df_financial.sort_values(by="timestamp", ascending=False)[
                            ["timestamp", "order_id", "customer_name", "customer_contact", "product_name", "quantity", "price", "total"]
                        ].rename(columns={
                                "timestamp": "Tanggal & Waktu",
                                "order_id": "ID Pesanan",
                                "customer_name": "Nama Pembeli",
                                "customer_contact": "Kontak Pembeli",
                                "product_name": "Nama Produk",
                                "quantity": "Jumlah",
                                "price": "Harga Satuan",
                                "total": "Total"
                            })
                        towrite = io.BytesIO()
                        with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
                            df_to_save.to_excel(writer, index=False, sheet_name='Laporan Keuangan')
                            
                        towrite.seek(0)
                        vendor_name = st.session_state.get("vendor_name", "Vendor")
                        st.download_button(
                            label="⬇️ Download Laporan Excel",
                            data=towrite,
                            file_name = f"Laporan Keuangan {vendor_name}.xlsx".replace(" ", "_"),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.info("Tidak ada data transaksi sesuai filter yang dipilih.")
        
            except Exception as e:
                st.error("Gagal memuat laporan keuangan.")
                st.write(e)


# =================================================================
# --- HALAMAN VERIFIKASI ADMIN ---
# =================================================================
elif role == 'admin':
    if menu_selection == "Verifikasi Pendaftar":
        if not st.session_state.get('logged_in') or not st.session_state.get('is_admin', False):
            st.warning("Silakan login sebagai admin untuk mengakses Verifikasi Pendaftar.")
            login_form()
            st.error("Halaman ini hanya dapat diakses oleh admin.")
            st.stop()
        else:
            st.sidebar.success(f"Login sebagai: **Administrator**")
            logout()  # ❗️Panggilan hanya satu kali, aman
    
    with st.expander("🛂 Verifikasi Pendaftar Vendor"):
    
        vendors_df = get_data("Vendors")
        vendors_ws = get_worksheet("Vendors")
    
        pending_vendors = vendors_df[vendors_df['status'].str.lower() == "pending"]
    
        if pending_vendors.empty:
            st.info("Tidak ada vendor yang menunggu persetujuan.")
        else:
            for idx, row in pending_vendors.iterrows():
                st.markdown("---")
                st.markdown(f"**{row['vendor_name']}** (`{row['username']}`)")
                st.caption(f"📱 {row['whatsapp_number']}")
    
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✅ Setujui {row['username']}", key=f"approve_{row['username']}"):
                        status_col_index = vendors_df.columns.get_loc('status') + 1
                        cell = vendors_ws.find(row['username'])
                        if cell:
                            vendors_ws.update_cell(cell.row, status_col_index, "approved")
                            st.cache_data.clear()  # ✅ Hapus cache data agar data terbaru muncul
                            st.success(f"Akun '{row['username']}' telah disetujui.")
                            st.rerun()
                with col2:
                    if st.button(f"❌ Tolak {row['username']}", key=f"reject_{row['username']}"):
                        status_col_index = vendors_df.columns.get_loc('status') + 1
                        cell = vendors_ws.find(row['username'])
                        if cell:
                            vendors_ws.update_cell(cell.row, status_col_index, "rejected")
                            st.cache_data.clear()  # ✅ Wajib
                            st.warning(f"Akun '{row['username']}' telah ditolak.")
                            st.rerun()

    with st.expander("🛠️ Kelola Status Vendor"):
        vendors_df = get_data("Vendors")
        st.dataframe(vendors_df[["vendor_id", "vendor_name", "is_active"]])
        
        selected_vendor_id = st.selectbox("Pilih Vendor", vendors_df['vendor_id'])
        current_status = vendors_df[vendors_df['vendor_id'] == selected_vendor_id]['is_active'].values[0]
        
        new_status = st.radio("Status Vendor", [True, False], index=0 if current_status else 1, format_func=lambda x: "Aktif" if x else "Nonaktif")
        
        if st.button("💾 Perbarui Status"):
            vendors_ws = get_worksheet("Vendors")
            cell = vendors_ws.find(selected_vendor_id)
            if cell:
                row_idx = cell.row
                # Misalnya kolom `is_active` ada di kolom D (kolom ke-4)
                vendors_ws.update_cell(row_idx, 7, str(new_status))
                st.success(f"Status vendor {selected_vendor_id} berhasil diperbarui ke: {'Aktif' if new_status else 'Nonaktif'}")
                st.cache_data.clear()
                st.rerun()

    with st.expander("🔍 Cari Vendor untuk Reset Password"):
        search_term = st.text_input("Cari berdasarkan username atau nama vendor")
        
        if search_term:
            filtered_vendors = vendors_df[
                vendors_df['username'].str.contains(search_term, case=False, na=False) |
                vendors_df['vendor_name'].str.contains(search_term, case=False, na=False)
            ]
        
            if filtered_vendors.empty:
                st.warning("Vendor tidak ditemukan.")
            else:
                selected_username = st.selectbox(
                    "Pilih Vendor",
                    filtered_vendors['username'].tolist()
                )
        
                if selected_username:
                    vendor_row = filtered_vendors[filtered_vendors['username'] == selected_username].iloc[0]
                    st.markdown(f"**{vendor_row['vendor_name']}** (`{vendor_row['username']}`) - Status: {vendor_row['status']}")
        
                    new_password = st.text_input("Password Baru", type="password", key=f"reset_pass_{selected_username}")
        
                    if st.button("Setel Ulang Password", key=f"btn_reset_{selected_username}"):
                        if not new_password:
                            st.error("Password baru tidak boleh kosong.")
                        else:
                            hashed_new_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                            password_col_index = vendors_df.columns.get_loc('password_hash') + 1
                            cell = vendors_ws.find(selected_username)
                            if cell:
                                vendors_ws.update_cell(cell.row, password_col_index, hashed_new_pw)
                                get_data.clear()  # Clear cache data get_data saja
                                st.success(f"Password untuk '{selected_username}' berhasil direset.")
                                st.rerun()
                            else:
                                st.error("Gagal menemukan akun vendor.")

        else:
            st.info("Masukkan nama atau username vendor untuk mencari.")
