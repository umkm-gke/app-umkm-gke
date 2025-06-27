import streamlit as st
import pandas as pd
import uuid, json, os, io, re, logging
from datetime import datetime
from urllib.parse import quote_plus
import bcrypt
from g_sheets import get_data, get_worksheet
from auth import login_form, logout
from streamlit_option_menu import option_menu
from PIL import Image
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
import streamlit.components.v1 as components


def get_all_orders():
        ws = get_worksheet("Orders")
        if not ws:
            return None, pd.DataFrame()
        try:
            df = pd.DataFrame(ws.get_all_records())
            return ws, df
        except Exception as e:
            st.error(f"❌ Gagal mengambil data dari worksheet: {e}")
            return None, pd.DataFrame()

# Fungsi filter pesanan vendor
def load_relevant_orders(df_orders_all, vendor_id):
        # Konversi timestamp dengan pengecekan tz-aware atau tidak
        def localize_or_convert_tz(series, tz):
            dt_series = pd.to_datetime(series, errors='coerce')
            if dt_series.dt.tz is None:
                return dt_series.dt.tz_localize(tz)
            else:
                return dt_series.dt.tz_convert(tz)
                    
# Configuration       
cloudinary.config( 
    cloud_name = "dehimmmo1", 
    api_key = "452435813679954", 
    api_secret = "UfXZPc7SQ_wl8jT5rC7LiZEZzdo", # Click 'View API Keys' above to copy your API secret
    secure=True
)
def resize_with_padding(image: Image.Image, target_size=(225, 225), background=(255, 255, 255, 0)) -> Image.Image:
    """
    Resize image ke target_size tanpa crop. 
    Tambah padding jika rasio berbeda. Bisa latar putih (RGB) atau transparan (RGBA).
    """
    image = image.convert("RGBA")  # Supaya bisa transparan atau full warna
    image.thumbnail(target_size, Image.LANCZOS)

    new_img = Image.new("RGBA", target_size, background)
    paste_position = (
        (target_size[0] - image.width) // 2,
        (target_size[1] - image.height) // 2
    )
    new_img.paste(image, paste_position, image)
    return new_img

def upload_to_cloudinary(pil_image: Image.Image, public_id=None, format="PNG"):
    # Konversi ke RGB jika target format JPEG (tidak mendukung alpha channel)
    if format.upper() == "JPEG" and pil_image.mode == "RGBA":
        pil_image = pil_image.convert("RGB")

    buffered = io.BytesIO()
    pil_image.save(buffered, format=format)
    buffered.seek(0)

    try:
        response = cloudinary.uploader.upload(
            buffered,
            resource_type="image",
            public_id=public_id,
            folder="produk",
            overwrite=True,
            format=format.lower()
        )
        return response.get("secure_url")
    except Exception as e:
        print("Upload error:", e)
        return None


# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# Timezone Jakarta
try:
    from zoneinfo import ZoneInfo
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

# Timestamp global
timestamp = format_jakarta(now_jakarta())

def is_valid_wa_number(number: str) -> bool:
            return re.fullmatch(r"62\d{10,11}", number) is not None

# Page & session setup
st.set_page_config(page_title="Marketplace Gading Kirana", layout="wide")
session_defaults = {'role':'guest','logged_in':False,'is_admin':False,'cart':[], 'action_log': {}}
for k,v in session_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def set_role_after_login():
    if st.session_state.get("logged_in"):
        st.session_state.role = 'admin' if st.session_state.is_admin else 'vendor'
    else:
        st.session_state.role = 'guest'
set_role_after_login()

def check_rate_limit(action, limit=5, period=60):
    now = datetime.utcnow().timestamp()
    hist = st.session_state.action_log.get(action, [])
    hist = [t for t in hist if now-t < period]
    if len(hist) >= limit:
        return False
    hist.append(now)
    st.session_state.action_log[action] = hist
    return True

def add_to_cart(product):
    if not check_rate_limit("add_to_cart", 10, 60):
        st.warning("Terlalu banyak aksi dalam waktu singkat. Tunggu sebentar.")
        return
    cart = st.session_state.cart
    for item in cart:
        if item['product_id'] == product['product_id']:
            item['quantity'] += 1
            st.toast(f"Jumlah {product['product_name']} meningkat", icon="🛒")
            return
    cart.append({'product_id':product['product_id'],'product_name':product['product_name'],
                 'price':product['price'],'vendor_id':product['vendor_id'],'quantity':1})
    st.toast(f"{product['product_name']} ditambahkan ke keranjang", icon="✅")


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
    username = st.text_input("Username")
    new_password = st.text_input("Password Baru", type="password")
    confirm_password = st.text_input("Konfirmasi Password", type="password")
    submit = st.button("Ajukan Reset Password")
    
    if submit:
        if not all([username, new_password, confirm_password]):
            st.warning("Semua kolom wajib diisi.")
        elif new_password != confirm_password:
            st.warning("Password dan konfirmasi tidak cocok.")
        else:
            vendors_df = get_data("Vendors")
            vendor_data = vendors_df[vendors_df['username'] == username]
    
            if vendor_data.empty:
                st.error("Username tidak ditemukan.")
            else:
                hashed_new_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                vendors_ws = get_worksheet("Vendors")
                cell = vendors_ws.find(username)
                if cell:
                    new_pw_col = vendors_df.columns.get_loc("new_password_hash") + 1
                    status_col = vendors_df.columns.get_loc("reset_status") + 1
                    vendors_ws.update_cell(cell.row, new_pw_col, hashed_new_pw)
                    vendors_ws.update_cell(cell.row, status_col, "pending")
                    st.success("✅ Permintaan reset password dikirim. Silakan hubungi admin via WhatsApp.")
                    st.cache_data.clear()


# --- NAVIGASI ---
with st.sidebar:
    # Safe default: guest
    role = st.session_state.get("role", "guest")

    # Ambil data vendor hanya jika bukan admin
    vendors = get_data("Vendors") if role != 'admin' else pd.DataFrame()

    # Hitung pending approval
    if not vendors.empty and 'status' in vendors.columns:
        pending = (vendors['status'].str.lower() == 'pending').sum()
    else:
        pending = 0

    # Definisi menu dan ikon sesuai role
    if role == 'admin':
        menu_items = [f"Verifikasi Pendaftar ({pending})"] if pending else ["Verifikasi Pendaftar"]
        icons = ["shield-lock"]
    elif role == 'vendor':
        menu_items = ["Portal Penjual"]
        icons = ["box-seam"]
    else:
        menu_items = ["Belanja", "Keranjang", "Daftar sebagai Penjual", "Reset Password"]
        icons = ["shop", "cart", "person-plus", "key"]

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
    ws_orders, df_all = get_all_orders()  # fungsi ambil data dari worksheet
    if df_all.empty:
        st.warning("Tidak ada data pesanan ditemukan.")
        df_all = None  # supaya bisa dicek berikutnya

    # Logout tombol ditampilkan jika login
    if st.session_state.get("logged_in"):
        st.sidebar.success(f"Login sebagai: **{st.session_state.get('vendor_name', 'User')}**")
        role = st.session_state.get("role")
        if role == "vendor":
                vendor_id = st.session_state.get('vendor_id')
        
                # --- Notifikasi Pesanan Baru ---
                jumlah_baru = 0
                if df_all is not None and not df_all.empty:
                    df_baru = df_all[df_all["order_status"] == "Baru"].copy()
                    for _, row in df_baru.iterrows():
                        try:
                            items = json.loads(row["order_details"])
                            for item in items:
                                if item.get("vendor_id") == vendor_id:
                                    jumlah_baru += 1
                                    break
                        except:
                            continue
        
                if jumlah_baru > 0:
                    st.sidebar.success(f"🚨 Anda memiliki **{jumlah_baru}** pesanan **Baru**!")
                else:
                    st.sidebar.info("🚨 Belum ada pesanan baru saat ini.")
        
                # --- Notifikasi Admin: Persetujuan Vendor & Reset Password ---
                
        elif role == "admin":
            try:
                vendors_df = get_data("Vendors")
        
                # Notifikasi verifikasi vendor
                pending_approval = vendors_df[vendors_df["status"].str.lower() == "pending"]
                if not pending_approval.empty:
                    st.sidebar.warning(f"🚨 Ada **{len(pending_approval)}** permintaan **verifikasi vendor**.")
                else:
                    st.sidebar.info("🚨 Tidak ada permintaan verifikasi vendor saat ini.")
        
                # Notifikasi reset password
                if "reset_status" in vendors_df.columns:
                    pending_reset = vendors_df[vendors_df["reset_status"].str.lower() == "pending"]
                    if not pending_reset.empty:
                        st.sidebar.warning(f"🚨 Ada **{len(pending_reset)}** permintaan **reset password vendor**.")
                    else:
                        st.sidebar.info("🚨 Tidak ada permintaan reset password vendor saat ini.")
                else:
                    st.sidebar.info("📄 Kolom reset_status belum tersedia di data vendor.")
            except Exception as e:
                st.sidebar.error("❌ Gagal mengambil data notifikasi admin.")

        logout()

    # Khusus guest & klik reset password
    if menu_selection == "Reset Password" and role == 'guest':
        reset_password_vendor()
        
# ========================
# --- HALAMAN BELANJA ---
# ========================
if st.session_state.role == 'guest' and menu_selection == "Belanja":
    st.markdown("### <img src='https://cdn-icons-png.flaticon.com/512/1170/1170678.png' width='25'/> Katalog Produk", unsafe_allow_html=True)
    st.markdown("_Temukan produk terbaik dari UMKM GKE_")

    # 1. Ambil data dan validasi
    try:
        products_df = get_data("Products")
        vendors_df = get_data("Vendors")
        orders_df = get_data("Orders")
        products_df['last_updated'] = pd.to_datetime(products_df['last_updated'], errors='coerce')
    except Exception as e:
        st.error("❌ Gagal memuat data. Silakan coba beberapa saat lagi.")
        st.stop()

    # Pastikan kolom kategori dan status tersedia
    products_df['category'] = products_df.get('category', "")
    products_df['is_active'] = products_df['is_active'].apply(lambda x: str(x).lower() == 'true')
    vendors_df['is_active'] = vendors_df['is_active'].apply(lambda x: str(x).lower() == 'true')

    # 2. Hitung penjualan
    sales = {}
    for det in orders_df.get('order_details', []).dropna():
        try:
            for item in json.loads(det):
                pid, qty = item['product_id'], int(item.get('quantity', 1))
                sales[pid] = sales.get(pid, 0) + qty
        except:
            continue

    # 3. Gabung data produk & vendor
    merged = products_df.merge(
        vendors_df[['vendor_id', 'vendor_name', 'is_active']],
        on='vendor_id', how='left', suffixes=('', '_v')
    )
    merged['sold_count'] = merged['product_id'].map(sales).fillna(0).astype(int)
    active_products = merged[merged['is_active'] & merged['is_active_v']]

    if active_products.empty:
        st.warning("Tidak ada produk aktif yang bisa ditampilkan.")
        st.stop()

    active_products = active_products.sort_values("sold_count", ascending=False)
    #st.markdown("### 🎯 Filter Pencarian")
    col1, col2, col3, col4 = st.columns([3, 3, 3, 3])
        
    with col1:
        query_params = st.experimental_get_query_params()
        url_vendor = query_params.get("vendor", [None])[0]
        vendor_list = sorted(active_products['vendor_name'].dropna().unique().tolist())
        default_vendor = url_vendor if url_vendor in vendor_list else "Semua"
        selected_vendor = st.selectbox("Pilih Penjual", ["Semua"] + vendor_list, index=(["Semua"] + vendor_list).index(default_vendor))
        
    with col2:
        kategori_list = sorted(active_products['category'].dropna().unique().tolist())
        selected_kategori = st.selectbox("Kategori", ["Semua"] + kategori_list)
        
    with col3:
        search_query = st.text_input("Cari Nama Produk")
        
    with col4:
        sort_option = st.selectbox("Urutkan Berdasarkan", [
        "Terlaris", "Terbaru", "Harga Termurah", "Harga Termahal"
        ])

    # 4. Sidebar Filter
    #st.sidebar.header("🔍 Filter Pencarian")
    #vendor_list = sorted(active_products['vendor_name'].dropna().unique().tolist())
    #selected_vendor = st.sidebar.selectbox("Pilih Penjual", ["Semua"] + vendor_list)

    #kategori_list = sorted(active_products['category'].dropna().unique().tolist())
    #selected_kategori = st.sidebar.selectbox("Kategori", ["Semua"] + kategori_list)

    #search_query = st.sidebar.text_input("Cari Nama Produk")
    #sort_option = st.sidebar.selectbox("Urutkan Berdasarkan", [
    #"Terlaris", "Terbaru", "Harga Termurah", "Harga Termahal"
    #])

    # 5. Terapkan filter
    filtered = active_products.copy()
    if selected_vendor != "Semua":
        filtered = filtered[filtered['vendor_name'] == selected_vendor]
        share_url = f"{st.secrets['base_url']}?vendor={selected_vendor.replace(' ', '%20')}"
        st.markdown("---")
        st.info(f"🔗 Link katalog untuk *{selected_vendor}*:\n`{share_url}`")
        st.code(share_url, language='markdown')
        st.caption("Bagikan link ini ke WA Group untuk promosi langsung ke katalog toko.")
        components.html(f"""
            <input type="text" value="{share_url}" id="copyURL" style="width: 80%; padding: 5px;">
            <button onclick="navigator.clipboard.writeText(document.getElementById('copyURL').value)">📋 Salin</button>
        """, height=50)
    if selected_kategori != "Semua":
        filtered = filtered[filtered['category'] == selected_kategori]
    if search_query:
        filtered = filtered[filtered['product_name'].str.contains(search_query, case=False, na=False)]
    if sort_option == "Terlaris":
        filtered = filtered.sort_values("sold_count", ascending=False)
    elif sort_option == "Terbaru":
        filtered = filtered.sort_values("last_updated", ascending=False)
    elif sort_option == "Harga Termurah":
        filtered = filtered.sort_values("price", ascending=True)
    elif sort_option == "Harga Termahal":
        filtered = filtered.sort_values("price", ascending=False)

    # 6. Tampilkan hasil produk
    if filtered.empty:
        st.warning("🚫 Tidak ada produk yang sesuai dengan filter.")
    else:
        st.markdown("---")
        #st.markdown("""
        #<style>
        #.product-card {
           # border: 1px solid #ddd;
           # border-radius: 8px;
           # padding: 8px 10px;
           # height: 100%;
           # box-sizing: border-box;
           # display: flex;
           # flex-direction: column;
           # justify-content: space-between;
       # }
       # .product-card .stImage { margin-bottom: 8px; }
       # .product-card .stButton > button { width: 100%; margin-top: 8px; }
       # .product-card .stCaption, .product-card .stMarkdown { margin-bottom: 4px; }
       # </style>
       # """, unsafe_allow_html=True)
        st.markdown("""
        <style>
        .custom-caption {
            line-height: 1.4em;
            margin-bottom: 2px;
            font-size: 0.9em;  /* Atur ukuran font di sini */
            font-weight: normal;
        }
        .custom-title {
            font-size: 1.2em;  /* Ini untuk judul produk */
            font-weight: bold;
            margin-bottom: 2px;
        }
        </style>
        """, unsafe_allow_html=True)


        rows = [filtered.iloc[i:i+4] for i in range(0, len(filtered), 4)]
        for row in rows:
            cols = st.columns(4)
            for col, (_, product) in zip(cols, row.iterrows()):
                with col:
                    with st.container():
                        #st.markdown('<div class="product-card">', unsafe_allow_html=True)
                        image_url = product.get('image_url', '')
                        try:
                            if hasattr(image_url, "read"):
                                st.image(image_url, use_container_width=True)
                            elif isinstance(image_url, str) and image_url.strip():
                                st.image(image_url.strip(), use_container_width=True)
                            else:
                                st.image("https://via.placeholder.com/200", use_container_width=True)
                        except:
                            st.image("https://via.placeholder.com/200", use_container_width=True)

                        try:
                            last_updated = pd.to_datetime(product.get('last_updated'), errors='coerce')
                            if pd.notnull(last_updated):
                                last_updated = last_updated.to_pydatetime()
                            is_new = pd.notnull(last_updated) and (now.date() - last_updated.date()).days <= 7
                        except Exception:
                            is_new = False
                        
                        # Debug sementara
                        #st.write({
                         #   "product": product['product_name'],
                          #  "last_updated": last_updated,
                           # "is_new": is_new
                        #})

                        new_badge = " <span style='color:green; font-size:0.9em;'>🆕 Produk Baru</span>" if is_new else ""
                        product_title = f"<div class='custom-title'>{product['product_name'][:30]}{new_badge}</div>"
                        st.markdown(product_title, unsafe_allow_html=True)
                        st.markdown(f"<div class='custom-caption'>Kategori: {product.get('category', '-')}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='custom-caption'>🧑 {product['vendor_name']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='custom-caption'>💰 Rp {int(product['price']):,}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='custom-caption'>✅ Terjual: {product['sold_count']:,}</div>", unsafe_allow_html=True)
                        
                        desc = product.get('description', '')
                        short_desc = desc[:60] + "..." if len(desc) > 60 else desc
                        st.markdown(f"<div class='custom-caption'>{short_desc}</div>", unsafe_allow_html=True)

                        #st.caption(desc[:60] + "..." if len(desc) > 60 else desc)

                        if st.button("➕ Tambah ke Keranjang", key=f"add_{product['product_id']}"):
                            add_to_cart(product)

                       # st.markdown('</div>', unsafe_allow_html=True)

    if 'cart' not in st.session_state:
        st.session_state.cart = []

#================================================
elif st.session_state.role == 'guest' and menu_selection == "Keranjang":
    st.header("🛒 Keranjang Belanja Anda")
    cart = st.session_state.cart

    if not cart:
        st.info("Keranjang Anda masih kosong. Yuk, mulai belanja!")
    else:
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
                product_note = st.text_input("Catatan Produk (opsional)", value=item.get("note", ""), key=f"note_{i}")
                cart[i]["note"] = product_note
                
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
            customer_contact = st.text_input(
                "Wajib diisi No WhatsApp Anda (Untuk konfirmasi pesanan)",
                placeholder="Contoh: 6281234567890 (11–12 digit)",
                max_chars=13,
                key="whatsapp_input_v3"
            )
            order_note = st.text_input("Catatan untuk Penjual (Opsional)", placeholder="Contoh: Kirim sore hari, Tanpa sambal.")
            submit_order = st.form_submit_button("Buat Pesanan Sekarang")
    
            if submit_order:
                if not customer_name or not customer_contact:
                    st.warning("Nama dan Nomor HP tidak boleh kosong.")
                    st.stop()
                elif not is_valid_wa_number(customer_contact):
                    st.error("❌ Nomor WhatsApp tidak valid. Gunakan format 628xxxxxxxxxx (11–12 digit angka saja).")
                    st.stop()
    
                with st.spinner("Memproses pesanan..."):
                    orders_ws = get_worksheet("Orders")
                    vendors_df = get_data("Vendors")
    
                    if orders_ws is None or vendors_df.empty:
                        st.error("Gagal memproses pesanan. Coba lagi.")
                        st.stop()
    
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
    
                    # Loop untuk masing-masing vendor
                    for vendor_id, amount in vendors_in_cart.items():
                        vendor_info_df = vendors_df[vendors_df['vendor_id'] == vendor_id]
                        if vendor_info_df.empty:
                            continue
                    
                        vendor_info = vendor_info_df.iloc[0]
                        vendor_name = vendor_info['vendor_name']
                        qris_url = str(vendor_info["qris_url"]).strip() if "qris_url" in vendor_info else ""
                        bank_info = str(vendor_info["bank_account"]).strip() if "bank_account" in vendor_info else ""
                        wa_number = str(vendor_info.get("whatsapp_number", "") if isinstance(vendor_info, dict) else vendor_info["whatsapp_number"]).strip()
                    
                        items = []
                        for item in cart:
                            if item['vendor_id'] == vendor_id:
                                item_line = f"{item['quantity']}x {item['product_name']}"
                                if item.get("note"):
                                    item_line += f" ({item['note']})"
                                items.append(item_line)

                        payment_info = ""
                    
                        st.markdown(f"### 🏪 {vendor_name}")
                        st.markdown(f"💰 **Total Tagihan: Rp {amount:,}**")
                    
                        if payment_method == "Transfer Bank":
                            if bank_info:
                                st.markdown(f"🏦 **Transfer ke Rekening:** `{bank_info}`")
                                st.info("Setelah transfer, konfirmasikan ke penjual melalui tombol WhatsApp di bawah.")
                                payment_info = f"Transfer ke Rekening: {bank_info}"
                            else:
                                st.warning("⚠️ Penjual belum menyediakan informasi rekening.")
                                payment_info = "Metode: Transfer Bank (rekening tidak tersedia)"
                    
                        elif payment_method == "QRIS":
                            if qris_url.lower().startswith("http") and qris_url.lower().endswith(('.jpg', '.jpeg', '.png')):
                                st.image(qris_url, caption="Scan QRIS Penjual", width=250)
                                st.info("Setelah scan dan bayar, klik tombol WhatsApp di bawah untuk konfirmasi.")
                                payment_info = "Metode: QRIS (lihat gambar)"
                            else:
                                st.warning("⚠️ QRIS belum tersedia dari penjual ini.")
                                payment_info = "Metode: QRIS (belum tersedia)"
                    
                        else:
                            st.success("📦 Pembayaran dilakukan saat barang diterima (COD).")
                            payment_info = "Metode: Tunai saat barang diterima"
                    
                        # Pesan WhatsApp otomatis
                        message = (
                            f"Halo {vendor_name}, saya *{customer_name}* ingin konfirmasi pesanan **{order_id}**.\n\n"
                            f"🛒 Pesanan:\n- " + "\n- ".join(items) + "\n\n"
                            f"💰 Total: Rp {amount:,}\n"
                            f"📌 {payment_info}"
                        )
                        if order_note:
                            message += f"\n📝 Catatan: {order_note}"

                        encoded_message = quote_plus(message)
                        whatsapp_url = f"https://wa.me/{wa_number}?text={encoded_message}"
                    
                        st.link_button(f"💬 Konfirmasi ke {vendor_name} via WhatsApp", whatsapp_url)
                        st.markdown("---")

    
                    # Kosongkan keranjang setelah selesai
                    st.session_state.cart = []


elif st.session_state.role == 'guest' and menu_selection == "Daftar sebagai Penjual":
    st.header("✍️ Pendaftaran Penjual Baru")
    st.write("Isi formulir di bawah ini untuk mulai berjualan di platform kami.")

    with st.form("vendor_registration_form", clear_on_submit=True):
        st.subheader("📝 Formulir Pendaftaran Penjual")
        st.caption("Silakan isi data di bawah ini untuk mulai berjualan di platform kami.")
    
        vendor_name = st.text_input("Nama Toko / UMKM Anda")
        username = st.text_input("Username (untuk login)")
        whatsapp_number = st.text_input(
            "Nomor WhatsApp (format: 628xxxxxxxxxx)",
            max_chars=13,
            placeholder="Contoh: 6281234567890"
        )
    
        bank_account = st.text_input(
            "Info Rekening Bank (WAJIB)",
            placeholder="Contoh: BCA - 1234567890 a.n. Toko ABC"
        )
    
        uploaded_qris = st.file_uploader("Upload Gambar QRIS (Opsional)", type=["jpg", "jpeg", "png"])
    
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Konfirmasi Password", type="password")
        submitted = st.form_submit_button("Daftar Sekarang")
    
        if submitted:
            if not all([vendor_name, username, whatsapp_number, bank_account, password, confirm_password]):
                st.warning("Semua kolom wajib diisi, kecuali QRIS.")
            elif not is_valid_wa_number(whatsapp_number):
                st.error("❌ Nomor WhatsApp tidak valid. Gunakan format 628xxxxxxxxxx.")
            elif password != confirm_password:
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
    
                            qris_url = ""
                            if uploaded_qris:
                                try:
                                    image = Image.open(uploaded_qris).convert("RGB")
                                    qris_url = upload_to_cloudinary(image, public_id=f"QRIS_{vendor_id}", format="JPEG")
                                    st.success("✅ QRIS berhasil diunggah.")
                                except Exception as e:
                                    st.warning(f"Gagal upload gambar QRIS: {e}")
    
                            new_vendor_row = [
                                vendor_id,
                                vendor_name,
                                username,
                                hashed_password,
                                whatsapp_number,
                                "pending",
                                "false",
                                bank_account,
                                qris_url
                            ]
                            vendors_ws.append_row(new_vendor_row)
                            st.success(
                                f"Pendaftaran berhasil, {vendor_name}! "
                                "Akun Anda sedang menunggu persetujuan admin. Silakan konfirmasi ke WA Admin"
                            )
                            st.balloons()
                            st.cache_data.clear()
                        else:
                            st.error("Gagal terhubung ke database. Coba lagi nanti.")
    
        # Bantuan vendor
        st.info("❓ Kesulitan upload QRIS? Kirim saja ke Admin via WhatsApp: 6281217026522")
with st.sidebar:
    if not st.session_state.get("logged_in"):
        st.markdown("### 🔐 Login Vendor / Admin")
        login_form()

# =================================================================
# --- HALAMAN PORTAL PENJUAL ---
# =================================================================
if role == 'vendor' and menu_selection == "Portal Penjual":

    # 1. Cek autentikasi
    if not st.session_state.get('logged_in') or st.session_state.get('role') != 'vendor':
        st.warning("Silakan login sebagai vendor untuk mengakses Portal Penjual.")
        #login_form()
        #st.stop()
    #else:
        #st.sidebar.success(f"Login sebagai: **{st.session_state.get('vendor_name', 'Guest')}**")
        #logout()


    vendor_id = st.session_state.get('vendor_id')
    if not vendor_id and not st.session_state.get('is_admin', False):
        st.error("Vendor ID tidak ditemukan.")
        st.stop()

    st.header(f"Dashboard: {st.session_state['vendor_name']}")

    # Fungsi ambil semua data
    @st.cache_data(ttl=300)
    def get_all_orders():
        ws = get_worksheet("Orders")
        if not ws:
            return None, pd.DataFrame()
        try:
            df = pd.DataFrame(ws.get_all_records())
            return ws, df
        except Exception as e:
            st.error(f"❌ Gagal mengambil data dari worksheet: {e}")
            return None, pd.DataFrame()

    # Fungsi filter pesanan vendor
    def load_relevant_orders(df_orders_all, vendor_id):
        # Konversi timestamp dengan pengecekan tz-aware atau tidak
        def localize_or_convert_tz(series, tz):
            dt_series = pd.to_datetime(series, errors='coerce')
            if dt_series.dt.tz is None:
                return dt_series.dt.tz_localize(tz)
            else:
                return dt_series.dt.tz_convert(tz)
    
        # Terapkan ke kolom timestamp
        df_orders_all['timestamp'] = localize_or_convert_tz(df_orders_all['timestamp'], jakarta_tz)
    
        # Filter pesanan 7 hari terakhir
        today = now_jakarta()
        last_week = today - pd.Timedelta(days=7)
        df_orders_all = df_orders_all[df_orders_all['timestamp'] >= last_week]
    
        grouped = []
    
        for _, row in df_orders_all.iterrows():
            try:
                items = json.loads(row['order_details'])
                relevant_items = []
                for item in items:
                    if item.get('vendor_id') == vendor_id:
                        relevant_items.append({
                            "product_name": item.get('product_name'),
                            "quantity": item.get('quantity'),
                            "price": item.get('price'),
                            "total_item_price": item.get('quantity') * item.get('price'),
                            "note": item.get("note", "")
                        })
                if relevant_items:
                    grouped.append({
                        "order_id": row['order_id'],
                        "items": relevant_items,
                        "customer_name": row['customer_name'],
                        "contact": row['customer_contact'],
                        "status": row['order_status'],
                        "timestamp": row['timestamp']
                    })
            except Exception as e:
                st.warning(f"⛔ Order ID {row['order_id']} gagal diproses: {e}")
    
        return pd.DataFrame(grouped)
        jumlah_baru = df_orders[df_orders["status"] == "Baru"].shape[0]
        if jumlah_baru > 0:
            st.success(f"🛎️ Anda memiliki **{jumlah_baru}** pesanan **Baru** yang belum diproses.")
        else:
            st.info("✅ Tidak ada pesanan baru saat ini.")
        
    #if st.button("🔄 Muat Ulang Data"):
     #   st.cache_data.clear()
      #  st.rerun()

    # Ambil data
    ws_orders, df_all = get_all_orders()
    if df_all.empty:
        st.warning("Tidak ada data pesanan ditemukan.")
        st.stop()
    
    # 3. Tampilan pesanan masuk
    with st.expander("📋 Daftar Pesanan Masuk", expanded=True):
        df_orders = load_relevant_orders(df_all, vendor_id)
    
        if df_orders.empty or "status" not in df_orders.columns:
            jumlah_baru = 0
            st.info("✅ Tidak ada pesanan baru saat ini.")
            df_orders = pd.DataFrame(columns=["order_id", "customer_name", "customer_contact", "order_details", "total", "status", "timestamp"])
            st.info("Belum ada pesanan yang masuk untuk Anda.")
        else:
            # Konversi timestamp
            df_orders['timestamp'] = pd.to_datetime(df_orders['timestamp'], errors='coerce')
            # Jika belum ada timezone, tetapkan Jakarta
            def ensure_jakarta_timezone(series):
                try:
                    return pd.to_datetime(series, errors='coerce').dt.tz_localize(jakarta_tz)
                except TypeError:
                    return pd.to_datetime(series, errors='coerce').dt.tz_convert(jakarta_tz)



    
            jumlah_baru = df_orders[df_orders["status"] == "Baru"].shape[0]
            if jumlah_baru > 0:
                st.success(f"🛎️ Anda memiliki **{jumlah_baru}** pesanan **Baru** yang belum diproses.")
            else:
                st.info("✅ Tidak ada pesanan baru saat ini.")
    
            # Filter tanggal
            today = now_jakarta()
            one_week_ago = today - pd.Timedelta(days=7)
    
            selected_date_range = st.date_input(
                "📆 Filter Rentang Tanggal Pesanan",
                value=(today.date(), today.date()),
                min_value=one_week_ago.date(),
                max_value=today.date()
            )
    
            if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
                start_date, end_date = selected_date_range
                df_orders = df_orders[
                    (df_orders['timestamp'].dt.date >= start_date) &
                    (df_orders['timestamp'].dt.date <= end_date)
                ]

            # Filter status
            filter_status = st.selectbox(
                "📌 Filter Status Pesanan",
                ["Semua", "Baru", "Diproses", "Selesai", "Dibatalkan"],
                index=1
            )
            if filter_status != "Semua":
                df_orders = df_orders[df_orders['status'] == filter_status]

            df_orders = df_orders.sort_values(by='timestamp', ascending=False).head(50)

            if df_orders.empty:
                st.info("Tidak ada pesanan sesuai filter.")
            else:
                for _, order in df_orders.iterrows():
                    with st.container(border=True):
                        st.write(f"📦 **Order ID:** `{order['order_id']}`")
                        st.write(f"🕒 Waktu: {order['timestamp']}")
                        st.write(f"👤 Pembeli: {order['customer_name']}")
                        st.write(f"📞 Kontak: {order['contact']}")
                        st.write(f"📌 Status: `{order['status']}`")
                
                        st.markdown("#### 🛒 Produk Dipesan:")
                        total_all = 0
                        for item in order['items']:
                            line = f"- {item['product_name']} x {item['quantity']} @ Rp {item['price']:,} = Rp {item['total_item_price']:,}"
                            if item.get("note"):
                                line += f" (Note: {item['note']})"
                            st.write(line)
                            total_all += item['total_item_price']
                        st.write(f"💰 **Total Harga yang Dipesan:** Rp {total_all:,}")
                
                        # Tombol WA
                        product_summary = "\n".join([
                            f"- {i['product_name']} x {i['quantity']} = Rp {i['total_item_price']:,}"
                            for i in order['items']
                        ])
                        wa_message = (
                            f"Halo {order['customer_name']}, kami dari tim penjual.\n"
                            f"Kami menerima pesanan Anda dengan ID {order['order_id']}:\n{product_summary}\n"
                            f"\nTotal: Rp {total_all:,}\n\n"
                            f"Silakan hubungi kami jika ada pertanyaan. Terima kasih!"
                        )
                        wa_link = f"https://wa.me/{order['contact']}?text={quote_plus(wa_message)}"
                        st.link_button("📲 Hubungi Pembeli via WhatsApp", wa_link)
    # 4. Modul Perubahan Status
    with st.expander("🔄 Pembaruan Status Pesanan"):
        df_vendor_orders = df_all[df_all["order_status"] == "Baru"].copy()
        df_vendor_orders["is_relevant"] = False
        
        for i, row in df_vendor_orders.iterrows():
            try:
                items = json.loads(row["order_details"])
                for item in items:
                    if item.get("vendor_id") == vendor_id:
                        df_vendor_orders.at[i, "is_relevant"] = True
                        break
            except:
                continue
        
        df_vendor_orders = df_vendor_orders[df_vendor_orders["is_relevant"]]
        
        if not df_vendor_orders.empty:
            #st.divider()
            #st.subheader("🔄 Perbarui Status Beberapa Pesanan")
        
            df_vendor_orders_display = df_vendor_orders[["order_id", "customer_name", "order_status"]].copy()
            df_vendor_orders_display["Pilih"] = False  # kolom checkbox
        
            edited_df = st.data_editor(
                df_vendor_orders_display,
                column_config={"Pilih": st.column_config.CheckboxColumn("Pilih")},
                hide_index=True,
                num_rows="dynamic",
                use_container_width=True,
            )
        
            selected_orders = edited_df[edited_df["Pilih"] == True]
        
            new_status = st.selectbox("Status Baru", ["Baru", "Diproses", "Selesai", "Dibatalkan"])
        
            if st.button("✅ Perbarui Status"):
                if selected_orders.empty:
                    st.warning("Silakan centang minimal satu pesanan.")
                else:
                    try:
                        orders_ws = get_worksheet("Orders")
                        success_count = 0
        
                        for order_id in selected_orders["order_id"]:
                            try:
                                df_index = df_all[df_all["order_id"] == order_id].index[0]
                                row_number = df_index + 2  # +2 karena header
                                orders_ws.update_cell(row_number, 6, new_status)
                                success_count += 1
                            except Exception as err:
                                st.warning(f"❌ Gagal update pesanan {order_id}: {err}")
        
                        st.success(f"✅ Berhasil memperbarui {success_count} pesanan ke status **{new_status}**.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error("❌ Gagal memperbarui status pesanan.")
                        st.exception(e)
        else:
            st.info("Belum ada pesanan 'Baru'")


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
        except Exception as e:
            st.error("Gagal memuat data produk.")
            st.write(e)
        # ------------------ TAMBAH / EDIT PRODUK ------------------
            with st.expander("➕ Tambah atau Edit Produk"):
                try:
                    # Ambil data produk seperti biasa
                    products_df = get_data("Products")
                    if 'category' not in products_df.columns:
                        products_df['category'] = ""
                    my_products = products_df[products_df['vendor_id'] == vendor_id]
                    existing_ids = my_products['product_id'].tolist()
                    
                    selected_product_id = st.selectbox(
                        "Pilih Produk untuk Diedit (kosongkan jika ingin tambah produk baru)",
                        [""] + existing_ids,
                        key="selected_product_id"
                    )
                    
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
                    
                    with st.form("product_form", clear_on_submit=True):
                        product_name = st.text_input("Nama Produk", value=default_name)
                        description = st.text_area("Deskripsi", value=default_desc)
                        price = st.number_input("Harga", min_value=0, value=default_price)
                        stock_quantity = st.number_input("Jumlah Stok", min_value=0, value=default_stock)
                        is_active = st.checkbox("Tampilkan Produk?", value=default_active)
                        kategori_list = ["Makanan", "Minuman", "Rumah Tangga", "Kesehatan", "Bayi", "Mainan", "Lainnya"]
                        kategori = st.selectbox(
                            "Kategori Produk",
                            options=kategori_list,
                            index=0 if not selected_product_id else (kategori_list.index(product_data['category']) if product_data['category'] in kategori_list else len(kategori_list) - 1)
                        )
                    
                        # Tampilkan gambar jika ada dan file ada di disk
                        def cloudinary_resize_url(original_url, width=225, height=225):
                            parts = original_url.split("/upload/")
                            if len(parts) != 2:
                                return original_url  # fallback jika bukan URL Cloudinary
                            return parts[0] + f"/upload/w_{width},h_{height},c_fit/" + parts[1]
                        
                        try:
                            if default_image:
                                if default_image.startswith("http"):
                                    resized_image_url = cloudinary_resize_url(default_image)
                                    st.image(resized_image_url, width=225, caption="Gambar Produk Saat Ini")
                                elif os.path.isfile(default_image):
                                    st.image(default_image, width=225, caption="Gambar Produk Saat Ini")
                                else:
                                    raise FileNotFoundError
                            else:
                                raise FileNotFoundError
                        except Exception as e:
                            st.warning("⚠️ Gambar tidak ditemukan. Menampilkan gambar default.")
                            st.image("https://placehold.co/225x225.png?text=No+Image&font=roboto", width=225)
                            st.caption(f"Error: {e}")
    
    
                    
                        uploaded_file = st.file_uploader("Upload Gambar Baru (opsional)", type=["jpg", "jpeg", "png"])
                    
                        submitted = st.form_submit_button("💾 Simpan Produk")
                    
                        if submitted:
                            if not product_name or not description:
                                st.warning("Nama produk dan deskripsi wajib diisi.")
                            else:
                                products_ws = get_worksheet("Products")
                        
                                image_url = default_image  # Default pakai gambar lama
                        
                                # Simpan gambar baru jika diupload
                                if uploaded_file:
                                    image = Image.open(uploaded_file)
                                
                                    # Resize tanpa crop
                                    resized_image = resize_with_padding(image, target_size=(225, 225), background=(255, 255, 255, 255))  # putih
                                
                                    # Tentukan format
                                    file_ext = uploaded_file.name.split('.')[-1].lower()
                                    file_format = "PNG" if file_ext == "png" else "JPEG"
                                
                                    # Jika JPEG, konversi ke RGB (JPEG tidak mendukung alpha channel)
                                    if file_format == "JPEG" and resized_image.mode == "RGBA":
                                        resized_image = resized_image.convert("RGB")
                                
                                    public_id = f"{vendor_id}_{uuid.uuid4().hex[:8]}"
                                    uploaded_url = upload_to_cloudinary(resized_image, public_id=public_id, format=file_format)
                                
                                    if uploaded_url:
                                        image_url = uploaded_url
                                        st.image(image_url, width=225, caption="Gambar Baru (225x225)")
                                        st.text(f"URL disimpan: {image_url}")
                                    else:
                                        st.warning("Gagal upload ke Cloudinary. Menggunakan gambar lama.")
                                        image_url = default_image
    
    
    
                        
                                product_id = selected_product_id if selected_product_id else f"PROD-{uuid.uuid4().hex[:6].upper()}"
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
                                #st.rerun()
        
                except Exception as e:
                    st.error("Gagal menampilkan form produk.")
                    st.write(e)
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
                                #st.rerun()
                            else:
                                st.error("Produk tidak ditemukan.")
                else:
                    st.caption("Belum ada produk yang bisa dihapus.")
    
 # ------------------ UPDATE DATA VENDOR ------------------
    
    with st.expander("✏️ Update Data Toko"):
        try:
            vendor_id = st.session_state.vendor_id
            vendors_df = get_data("Vendors")
            vendors_ws = get_worksheet("Vendors")
    
            vendor_info = vendors_df[vendors_df['vendor_id'] == vendor_id].iloc[0]
    
            updated_bank = st.text_input("Info Rekening Bank", value=vendor_info.get("bank_account", ""))
    
            st.caption("QRIS saat ini (jika tersedia):")
            if vendor_info.get("qris_url"):
                st.image(vendor_info.get("qris_url"), width=200)
    
            uploaded_qris = st.file_uploader("Upload Gambar QRIS Baru (opsional)", type=["jpg", "jpeg", "png"])
    
            if st.button("💾 Simpan Perubahan"):
                updated_qris_url = vendor_info.get("qris_url", "")
    
                if uploaded_qris:
                    try:
                        img = Image.open(uploaded_qris).convert("RGB")
                        public_id = f"QRIS_{vendor_id}"
                        updated_qris_url = upload_to_cloudinary(img, public_id=public_id, format="JPEG")
                        st.success("✅ QRIS berhasil diunggah.")
                    except Exception as e:
                        st.warning(f"Gagal upload QRIS: {e}")
    
                try:
                    cell = vendors_ws.find(vendor_id)
                    row = cell.row
    
                    vendors_ws.update_cell(row, 8, updated_bank)      # kolom H: bank_account
                    vendors_ws.update_cell(row, 9, updated_qris_url)  # kolom I: qris_url
    
                    st.success("✅ Data berhasil diperbarui.")
                    st.cache_data.clear()
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
            #st.stop()
        #else:
            #st.sidebar.success(f"Login sebagai: **Administrator**")
            #logout()  # ❗️Panggilan hanya satu kali, aman
        
    if st.button("🔄 Muat Ulang Data"):
        st.cache_data.clear()
        st.rerun()
            
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
                #st.rerun()

    with st.expander("🛡️ Persetujuan Reset Password Vendor"):
        vendors_df = get_data("Vendors")
        vendors_ws = get_worksheet("Vendors")
    
        reset_pending = vendors_df[vendors_df['reset_status'].str.lower() == "pending"]
    
        if reset_pending.empty:
            st.info("Tidak ada permintaan reset password.")
        else:
            for i, row in reset_pending.iterrows():
                st.markdown("---")
                st.markdown(f"**{row['vendor_name']}** (`{row['username']}`)")
                st.caption(f"📱 {row['whatsapp_number']}")
    
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✅ Setujui Reset - {row['username']}", key=f"approve_{row['username']}"):
                        cell = vendors_ws.find(row['username'])
                        if cell:
                            # Update password_hash
                            pw_col = vendors_df.columns.get_loc('password_hash') + 1
                            new_pw_col = vendors_df.columns.get_loc('new_password_hash') + 1
                            reset_col = vendors_df.columns.get_loc('reset_status') + 1
    
                            new_hashed_pw = row['new_password_hash']
                            vendors_ws.update_cell(cell.row, pw_col, new_hashed_pw)
                            vendors_ws.update_cell(cell.row, new_pw_col, "")  # kosongkan
                            vendors_ws.update_cell(cell.row, reset_col, "approved")
    
                            st.cache_data.clear()
                            st.success(f"Password untuk {row['username']} berhasil direset.")
                            st.rerun()
                with col2:
                    if st.button(f"❌ Tolak - {row['username']}", key=f"reject_{row['username']}"):
                        reset_col = vendors_df.columns.get_loc('reset_status') + 1
                        vendors_ws.update_cell(cell.row, reset_col, "rejected")
                        st.warning(f"Permintaan reset '{row['username']}' ditolak.")
                        st.rerun()

