import streamlit as st
import pandas as pd
import pymysql
import ssl
import uuid
import base64
from pathlib import Path
from datetime import date, timedelta, datetime

# =========================================================
# 1. CẤU HÌNH ỨNG DỤNG
# =========================================================

st.set_page_config(
    page_title="Charm Pearl Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE = Path(__file__).resolve().parent

HOTEL_NAME = "CHARM PEARL HOTEL"
LOCATION = "VŨNG TÀU"

LOGO = BASE / "IMG_LOGO11.jpg"
BANNER = BASE / "IMG_BANNER2.jpg"
BG = BASE / "IMG_NENCHIM3.jpg"

# =========================================================
# 2. THÔNG TIN MYSQL AIVEN
# =========================================================
# Theo yêu cầu: thông tin kết nối được đặt trực tiếp trong app.py.
# Lưu ý: nếu đưa file lên GitHub công khai, hãy đổi password Aiven.

DB_USER = "avnadmin"
DB_PASSWORD = "AVNS_TX2oBXmTGGjXba6p7j1"
DB_HOST = "mysql-3a5ef2bc-binhquytoc.a.aivencloud.com"
DB_PORT = 14483
DB_NAME = "charm_pearl_hotel"

# =========================================================
# 3. HẠNG PHÒNG
# =========================================================

ROOM_TYPES = {
    "Deluxe Room King": {
        "price": 850000,
        "capacity": 2,
        "beds": "1 giường King",
        "description": "Phòng nghỉ hiện đại dành cho 1–2 khách.",
        "images": ["DELUXEROOOMKING.jpg"],
    },
    "Deluxe Room Twins": {
        "price": 850000,
        "capacity": 2,
        "beds": "2 giường đơn",
        "description": "Phù hợp cho bạn bè hoặc khách công tác.",
        "images": ["DELUXEROOOMTWINS.jpg"],
    },
    "Premier Garden": {
        "price": 1100000,
        "capacity": 2,
        "beds": "1 giường King",
        "description": "Không gian nghỉ dưỡng hướng vườn.",
        "images": ["PREMIERGARDEN1.jpg", "PREMIERGARDEN2.jpg"],
    },
    "Premier Ocean": {
        "price": 1350000,
        "capacity": 2,
        "beds": "1 giường King",
        "description": "Phòng cao cấp với không gian hướng biển.",
        "images": ["PREMIEROCEAN1.jpg", "PREMIEROCEAN2.jpg"],
    },
    "Princess Suite": {
        "price": 1800000,
        "capacity": 3,
        "beds": "1 giường King",
        "description": "Suite rộng rãi dành cho kỳ nghỉ cao cấp.",
        "images": ["PRINCESSSUITE1.jpg", "PRINCESSSUITE2.jpg"],
    },
    "Royal Suite Villa": {
        "price": 3000000,
        "capacity": 6,
        "beds": "King + giường phụ",
        "description": "Villa cao cấp dành cho gia đình hoặc nhóm khách.",
        "images": [
            "ROYALSUITEVILLA1.jpg",
            "ROYALSUITEVILLA2.jpg",
            "ROYALSUITEVILLA3.jpg",
            "ROYALSUITEVILLA4.jpg",
        ],
    },
}

ROOM_STATUSES = ["Trống", "Đã đặt", "Đang ở", "Đang dọn", "Bảo trì"]
BOOKING_STATUSES = ["Đã đặt", "Đang ở", "Đã trả phòng", "Đã hủy"]

# =========================================================
# 4. HÀM TIỆN ÍCH
# =========================================================

def money(value):
    try:
        return f"{int(value or 0):,.0f}".replace(",", ".") + " VNĐ"
    except Exception:
        return "0 VNĐ"


def status_icon(status):
    return {
        "Trống": "🟢",
        "Đã đặt": "🟣",
        "Đang ở": "🔵",
        "Đang dọn": "🟡",
        "Bảo trì": "🔴",
        "Đã trả phòng": "⚪",
        "Đã hủy": "⚫",
    }.get(status, "⚪")


def safe_int(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def image_path(filename):
    path = BASE / filename
    return path if path.exists() else None


def image_to_base64(path):
    if not path or not path.exists():
        return None
    try:
        return base64.b64encode(path.read_bytes()).decode()
    except Exception:
        return None


def make_code(prefix):
    return f"{prefix}{datetime.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:4].upper()}"


# =========================================================
# 5. KẾT NỐI MYSQL AIVEN
# =========================================================

@st.cache_resource(show_spinner=False)
def get_connection():
    """
    Kết nối MySQL Aiven bằng PyMySQL.
    Aiven thường yêu cầu SSL. Bản này bật SSL nhưng không bắt buộc
    CA riêng để dễ chạy. Có thể bổ sung CA certificate nếu cần.
    """
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        conn = pymysql.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            connect_timeout=20,
            read_timeout=30,
            write_timeout=30,
            ssl=ssl_context,
        )
        return conn
    except Exception as e:
        st.error(f"Không thể kết nối MySQL Aiven: {e}")
        return None


def db_fetch(query, params=None):
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Lỗi truy vấn dữ liệu: {e}")
        return []


def db_fetch_one(query, params=None):
    rows = db_fetch(query, params)
    return rows[0] if rows else None


def db_execute(query, params=None, commit=True):
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            if commit:
                conn.commit()
            return True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        st.error(f"Lỗi cập nhật dữ liệu: {e}")
        return False


def db_execute_many(query, data, commit=True):
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.executemany(query, data)
            if commit:
                conn.commit()
            return True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        st.error(f"Lỗi cập nhật hàng loạt: {e}")
        return False


def db_insert_return_id(query, params=None):
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            new_id = cursor.lastrowid
            conn.commit()
            return new_id
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        st.error(f"Lỗi thêm dữ liệu: {e}")
        return None


# =========================================================
# 6. KHỞI TẠO DATABASE
# =========================================================

def initialize_database():
    conn = get_connection()
    if conn is None:
        return False

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    room_number VARCHAR(10) UNIQUE NOT NULL,
                    floor INT NOT NULL,
                    room_type VARCHAR(100) NOT NULL,
                    price BIGINT NOT NULL,
                    capacity INT NOT NULL,
                    status VARCHAR(30) DEFAULT 'Trống',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_rooms_floor (floor),
                    INDEX idx_rooms_status (status),
                    INDEX idx_rooms_type (room_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_code VARCHAR(40) UNIQUE NOT NULL,
                    full_name VARCHAR(150) NOT NULL,
                    phone VARCHAR(30),
                    email VARCHAR(150),
                    id_number VARCHAR(50),
                    nationality VARCHAR(80),
                    address VARCHAR(255),
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_customer_phone (phone),
                    INDEX idx_customer_name (full_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    booking_code VARCHAR(40) UNIQUE NOT NULL,
                    customer_id INT NULL,
                    room_number VARCHAR(10) NOT NULL,
                    customer_name VARCHAR(150) NOT NULL,
                    phone VARCHAR(30),
                    guests INT NOT NULL DEFAULT 1,
                    check_in DATE NOT NULL,
                    check_out DATE NOT NULL,
                    actual_check_in DATETIME NULL,
                    actual_check_out DATETIME NULL,
                    nights INT NOT NULL DEFAULT 1,
                    room_total BIGINT NOT NULL DEFAULT 0,
                    service_total BIGINT NOT NULL DEFAULT 0,
                    discount BIGINT NOT NULL DEFAULT 0,
                    grand_total BIGINT NOT NULL DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'Đã đặt',
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_booking_code (booking_code),
                    INDEX idx_booking_room (room_number),
                    INDEX idx_booking_status (status),
                    INDEX idx_booking_dates (check_in, check_out),
                    CONSTRAINT fk_booking_customer
                        FOREIGN KEY (customer_id) REFERENCES customers(id)
                        ON DELETE SET NULL ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(30) UNIQUE NOT NULL,
                    name VARCHAR(150) NOT NULL,
                    category VARCHAR(80) DEFAULT 'Khác',
                    price BIGINT NOT NULL DEFAULT 0,
                    active TINYINT(1) DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS booking_services (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    booking_id INT NOT NULL,
                    service_id INT NOT NULL,
                    quantity INT NOT NULL DEFAULT 1,
                    unit_price BIGINT NOT NULL DEFAULT 0,
                    total BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_bs_booking
                        FOREIGN KEY (booking_id) REFERENCES bookings(id)
                        ON DELETE CASCADE ON UPDATE CASCADE,
                    CONSTRAINT fk_bs_service
                        FOREIGN KEY (service_id) REFERENCES services(id)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
                    INDEX idx_bs_booking (booking_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    invoice_code VARCHAR(40) UNIQUE NOT NULL,
                    booking_id INT NOT NULL,
                    room_total BIGINT DEFAULT 0,
                    service_total BIGINT DEFAULT 0,
                    discount BIGINT DEFAULT 0,
                    grand_total BIGINT DEFAULT 0,
                    payment_method VARCHAR(50) DEFAULT 'Tiền mặt',
                    payment_status VARCHAR(50) DEFAULT 'Chưa thanh toán',
                    paid_at DATETIME NULL,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_invoice_booking
                        FOREIGN KEY (booking_id) REFERENCES bookings(id)
                        ON DELETE CASCADE ON UPDATE CASCADE,
                    INDEX idx_invoice_booking (booking_id),
                    INDEX idx_invoice_paid (payment_status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    sender VARCHAR(30) NOT NULL,
                    customer_name VARCHAR(100),
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_chat_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # -------------------------------------------------
            # Tạo 50 phòng mẫu nếu bảng đang trống
            # -------------------------------------------------
            cursor.execute("SELECT COUNT(*) AS total FROM rooms")
            room_count = cursor.fetchone()["total"]

            if room_count == 0:
                rooms = []
                for floor in range(1, 6):
                    for number in range(1, 11):
                        room_number = f"{floor}{number:02d}"

                        if number in [1, 2]:
                            room_type = "Deluxe Room King"
                        elif number in [3, 4]:
                            room_type = "Deluxe Room Twins"
                        elif number in [5, 6]:
                            room_type = "Premier Garden"
                        elif number in [7, 8]:
                            room_type = "Premier Ocean"
                        elif number == 9:
                            room_type = "Princess Suite"
                        else:
                            room_type = "Royal Suite Villa"

                        info = ROOM_TYPES[room_type]
                        rooms.append(
                            (
                                room_number,
                                floor,
                                room_type,
                                info["price"],
                                info["capacity"],
                                "Trống",
                            )
                        )

                cursor.executemany("""
                    INSERT INTO rooms
                    (room_number, floor, room_type, price, capacity, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, rooms)

            # -------------------------------------------------
            # Dịch vụ mặc định
            # -------------------------------------------------
            cursor.execute("SELECT COUNT(*) AS total FROM services")
            service_count = cursor.fetchone()["total"]

            if service_count == 0:
                services = [
                    ("DV001", "Ăn sáng", "Ẩm thực", 120000),
                    ("DV002", "Cà phê", "Ẩm thực", 50000),
                    ("DV003", "Giặt ủi", "Housekeeping", 80000),
                    ("DV004", "Minibar", "Ẩm thực", 100000),
                    ("DV005", "Extra Bed", "Phòng", 250000),
                    ("DV006", "Spa", "Wellness", 350000),
                    ("DV007", "Đưa đón sân bay", "Vận chuyển", 400000),
                    ("DV008", "Room Service", "Ẩm thực", 150000),
                    ("DV009", "Late Check-out", "Phòng", 300000),
                ]
                cursor.executemany("""
                    INSERT INTO services
                    (code, name, category, price)
                    VALUES (%s, %s, %s, %s)
                """, services)

        conn.commit()
        return True

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        st.error(f"Không thể khởi tạo database: {e}")
        return False


# =========================================================
# 7. CẬP NHẬT TRẠNG THÁI PHÒNG TỰ ĐỘNG
# =========================================================

def sync_room_statuses():
    """
    Nếu booking đã hết hạn nhưng vẫn đang ở trạng thái Đã đặt,
    chuyển phòng về Trống. Không tự động thay đổi phòng Đang ở.
    """
    today = date.today()

    expired = db_fetch("""
        SELECT id, room_number
        FROM bookings
        WHERE status = 'Đã đặt'
          AND check_out < %s
    """, (today,))

    for booking in expired:
        db_execute(
            "UPDATE bookings SET status='Đã trả phòng' WHERE id=%s",
            (booking["id"],),
        )
        db_execute(
            "UPDATE rooms SET status='Trống' WHERE room_number=%s",
            (booking["room_number"],),
        )


# =========================================================
# 8. CSS
# =========================================================

st.markdown("""
<style>
.stApp {
    font-family: Arial, sans-serif;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #063448, #0a5368, #08394b);
}

section[data-testid="stSidebar"] * {
    color: white !important;
}

.hero {
    background: rgba(255,255,255,0.95);
    border-radius: 22px;
    padding: 25px;
    box-shadow: 0 5px 25px rgba(0,0,0,0.08);
    margin-bottom: 20px;
}

.hero-title {
    font-size: 38px;
    font-weight: 800;
    color: #103f52;
    letter-spacing: 2px;
}

.hero-sub {
    color: #72838c;
    font-size: 16px;
}

.card {
    background: rgba(255,255,255,0.96);
    padding: 20px;
    border-radius: 16px;
    box-shadow: 0 3px 15px rgba(0,0,0,0.08);
    min-height: 105px;
}

.card-title {
    color: #71828a;
    font-size: 14px;
}

.card-number {
    color: #123d4d;
    font-size: 25px;
    font-weight: 800;
    margin-top: 7px;
}

.room-card {
    background: rgba(255,255,255,0.97);
    border-radius: 16px;
    padding: 15px;
    margin-bottom: 12px;
    border: 1px solid #e2e8eb;
    box-shadow: 0 3px 10px rgba(0,0,0,0.06);
}

.room-number {
    color: #123d4d;
    font-size: 22px;
    font-weight: 800;
}

.room-type {
    color: #70818a;
    font-size: 13px;
}

.section-title {
    font-size: 25px;
    font-weight: 800;
    color: #123d4d;
    margin-top: 20px;
    margin-bottom: 15px;
}

.small-muted {
    color: #6c7a80;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

bg64 = image_to_base64(BG)
if bg64:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image:
                linear-gradient(
                    rgba(246,249,250,0.94),
                    rgba(246,249,250,0.94)
                ),
                url("data:image/jpeg;base64,{bg64}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# 9. KẾT NỐI / KHỞI TẠO
# =========================================================

if "db_ready" not in st.session_state:
    st.session_state.db_ready = False

if not st.session_state.db_ready:
    st.session_state.db_ready = initialize_database()

if st.session_state.db_ready:
    sync_room_statuses()


# =========================================================
# 10. SIDEBAR
# =========================================================

with st.sidebar:
    if LOGO.exists():
        st.image(str(LOGO), width=95)

    st.markdown("## CHARM PEARL HOTEL")
    st.caption("HOTEL MANAGEMENT SYSTEM")

    if st.session_state.db_ready:
        st.success("MySQL Aiven: Đã kết nối")
    else:
        st.error("MySQL Aiven: Chưa kết nối")

    st.divider()

    menu = st.radio(
        "MENU QUẢN LÝ",
        [
            "🏠 Dashboard",
            "🛏️ Quản lý phòng",
            "📷 Hạng phòng",
            "📅 Đặt phòng",
            "🛎️ Check-in",
            "🚪 Check-out",
            "👥 Khách hàng",
            "🍽️ Dịch vụ",
            "🧾 Hóa đơn",
            "💰 Doanh thu",
            "💬 Chat với khách",
            "📊 Báo cáo",
        ],
    )

    st.divider()
    st.caption(HOTEL_NAME)
    st.caption(LOCATION)
    st.caption("50 phòng · 5 tầng")


if not st.session_state.db_ready:
    st.error(
        "Chưa kết nối được MySQL Aiven. "
        "Kiểm tra DB_HOST, DB_PORT, DB_USER, DB_PASSWORD và DB_NAME."
    )
    st.stop()


# =========================================================
# 11. DASHBOARD
# =========================================================

if menu == "🏠 Dashboard":
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">CHARM PEARL HOTEL</div>
            <div class="hero-sub">
                Hotel Management System · Vũng Tàu
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if BANNER.exists():
        _, center, _ = st.columns([1, 2.5, 1])
        with center:
            st.image(str(BANNER), use_container_width=True)

    rooms = pd.DataFrame(
        db_fetch("""
            SELECT * FROM rooms
            ORDER BY floor, room_number
        """)
    )

    bookings = pd.DataFrame(
        db_fetch("""
            SELECT * FROM bookings
            ORDER BY id DESC
        """)
    )

    total_rooms = len(rooms)
    empty_rooms = int((rooms["status"] == "Trống").sum()) if not rooms.empty else 0
    reserved_rooms = int((rooms["status"] == "Đã đặt").sum()) if not rooms.empty else 0
    occupied_rooms = int((rooms["status"] == "Đang ở").sum()) if not rooms.empty else 0
    cleaning_rooms = int((rooms["status"] == "Đang dọn").sum()) if not rooms.empty else 0

    revenue = 0
    if not bookings.empty and "grand_total" in bookings.columns:
        revenue = bookings.loc[
            bookings["status"].isin(["Đã trả phòng", "Đang ở", "Đã đặt"]),
            "grand_total",
        ].fillna(0).sum()

    cards = st.columns(5)
    dashboard_data = [
        ("🏨", "Tổng phòng", total_rooms),
        ("🟢", "Phòng trống", empty_rooms),
        ("🟣", "Đã đặt", reserved_rooms),
        ("🔵", "Đang ở", occupied_rooms),
        ("💰", "Doanh thu", money(revenue)),
    ]

    for col, item in zip(cards, dashboard_data):
        with col:
            st.markdown(
                f"""
                <div class="card">
                    <div class="card-title">{item[0]} {item[1]}</div>
                    <div class="card-number">{item[2]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="section-title">Sơ đồ phòng</div>',
        unsafe_allow_html=True,
    )

    floor = st.selectbox("Chọn tầng", ["Tất cả", 1, 2, 3, 4, 5])

    show_rooms = rooms.copy()
    if floor != "Tất cả" and not show_rooms.empty:
        show_rooms = show_rooms[show_rooms["floor"] == floor]

    cols = st.columns(5)
    for i, (_, room) in enumerate(show_rooms.iterrows()):
        with cols[i % 5]:
            st.markdown(
                f"""
                <div class="room-card">
                    <div class="room-number">🛏️ {room["room_number"]}</div>
                    <div class="room-type">
                        {room["room_type"]} · Tầng {room["floor"]}
                    </div>
                    <p>{money(room["price"])} / đêm</p>
                    <b>{status_icon(room["status"])} {room["status"]}</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.info(f"Phòng đang dọn: {cleaning_rooms}")


# =========================================================
# 12. HẠNG PHÒNG
# =========================================================

elif menu == "📷 Hạng phòng":
    st.title("📷 Các hạng phòng")

    for room_type, info in ROOM_TYPES.items():
        st.markdown(f"## {room_type}")

        valid_images = [
            image_path(name) for name in info["images"]
            if image_path(name)
        ]

        if valid_images:
            columns = st.columns(min(3, len(valid_images)))
            for i, image in enumerate(valid_images):
                with columns[i % len(columns)]:
                    st.image(str(image), use_container_width=True)
        else:
            st.info("Chưa có hình ảnh trong thư mục ứng dụng.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Giá phòng", money(info["price"]))
        c2.metric("Sức chứa", f'{info["capacity"]} khách')
        c3.metric("Giường", info["beds"])
        st.write(info["description"])
        st.divider()


# =========================================================
# 13. QUẢN LÝ PHÒNG
# =========================================================

elif menu == "🛏️ Quản lý phòng":
    st.title("🛏️ Quản lý phòng")

    rooms = pd.DataFrame(
        db_fetch("""
            SELECT id, room_number, floor, room_type,
                   price, capacity, status
            FROM rooms
            ORDER BY floor, room_number
        """)
    )

    if rooms.empty:
        st.warning("Chưa có dữ liệu phòng.")
        st.stop()

    c1, c2, c3 = st.columns(3)

    with c1:
        floor_filter = st.selectbox(
            "Tầng", ["Tất cả", 1, 2, 3, 4, 5], key="room_floor_filter"
        )

    with c2:
        type_filter = st.selectbox(
            "Hạng phòng",
            ["Tất cả"] + list(ROOM_TYPES.keys()),
            key="room_type_filter",
        )

    with c3:
        status_filter = st.selectbox(
            "Trạng thái",
            ["Tất cả"] + ROOM_STATUSES,
            key="room_status_filter",
        )

    result = rooms.copy()

    if floor_filter != "Tất cả":
        result = result[result["floor"] == floor_filter]
    if type_filter != "Tất cả":
        result = result[result["room_type"] == type_filter]
    if status_filter != "Tất cả":
        result = result[result["status"] == status_filter]

    display = result.rename(
        columns={
            "room_number": "Phòng",
            "floor": "Tầng",
            "room_type": "Hạng phòng",
            "price": "Giá",
            "capacity": "Sức chứa",
            "status": "Trạng thái",
        }
    )

    st.dataframe(display, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Cập nhật trạng thái phòng")

    with st.form("update_room_form"):
        room = st.selectbox("Phòng", rooms["room_number"].tolist())
        new_status = st.selectbox("Trạng thái mới", ROOM_STATUSES)
        submit = st.form_submit_button(
            "CẬP NHẬT",
            use_container_width=True,
        )

    if submit:
        # Không cho chuyển thủ công sang Trống nếu đang có khách ở.
        current = db_fetch_one(
            "SELECT status FROM rooms WHERE room_number=%s",
            (room,),
        )
        if current and current["status"] == "Đang ở" and new_status == "Trống":
            st.error("Phòng đang có khách. Hãy thực hiện Check-out trước.")
        else:
            if db_execute(
                "UPDATE rooms SET status=%s WHERE room_number=%s",
                (new_status, room),
            ):
                st.success(f"Phòng {room} đã chuyển sang {new_status}.")
                st.rerun()


# =========================================================
# 14. ĐẶT PHÒNG
# =========================================================

elif menu == "📅 Đặt phòng":
    st.title("📅 Đặt phòng")

    c1, c2 = st.columns(2)

    with c1:
        check_in = st.date_input("Ngày check-in", date.today())

    with c2:
        check_out = st.date_input(
            "Ngày check-out",
            date.today() + timedelta(days=1),
        )

    if check_out <= check_in:
        st.error("Ngày check-out phải sau ngày check-in.")
        st.stop()

    nights = (check_out - check_in).days

    room_type = st.selectbox(
        "Hạng phòng",
        list(ROOM_TYPES.keys()),
    )

    info = ROOM_TYPES[room_type]

    images = [
        image_path(name) for name in info["images"]
        if image_path(name)
    ]

    if images:
        st.image(str(images[0]), width=500)

    st.write(info["description"])

    # Kiểm tra phòng không có booking giao với khoảng ngày đã chọn.
    available_data = db_fetch(
        """
        SELECT r.*
        FROM rooms r
        WHERE r.room_type=%s
          AND r.status NOT IN ('Đang ở', 'Đang dọn', 'Bảo trì')
          AND NOT EXISTS (
              SELECT 1
              FROM bookings b
              WHERE b.room_number = r.room_number
                AND b.status IN ('Đã đặt', 'Đang ở')
                AND b.check_in < %s
                AND b.check_out > %s
          )
        ORDER BY r.room_number
        """,
        (room_type, check_out, check_in),
    )

    available = pd.DataFrame(available_data)

    if available.empty:
        st.error("Không còn phòng phù hợp trong khoảng thời gian này.")
        st.stop()

    room = st.selectbox(
        "Chọn phòng",
        available["room_number"].tolist(),
    )

    st.success(f"Còn {len(available)} phòng phù hợp thuộc hạng {room_type}.")

    c1, c2 = st.columns(2)

    with c1:
        guest = st.text_input("Tên khách *")
        phone = st.text_input("Số điện thoại *")
        email = st.text_input("Email")
        id_number = st.text_input("CCCD/Hộ chiếu")

    with c2:
        guests = st.number_input(
            "Số khách",
            min_value=1,
            max_value=info["capacity"],
            value=1,
        )
        nationality = st.text_input("Quốc tịch")
        address = st.text_input("Địa chỉ")
        note = st.text_area("Ghi chú")

    room_total = info["price"] * nights

    st.info(
        f"Phòng: {room}\n\n"
        f"Số đêm: {nights}\n\n"
        f"Tiền phòng: {money(room_total)}"
    )

    if st.button("📅 XÁC NHẬN ĐẶT PHÒNG", use_container_width=True):
        if not guest.strip() or not phone.strip():
            st.warning("Vui lòng nhập tên khách và số điện thoại.")
            st.stop()

        # Tạo / cập nhật khách hàng.
        customer = db_fetch_one(
            "SELECT id FROM customers WHERE phone=%s LIMIT 1",
            (phone.strip(),),
        )

        if customer:
            customer_id = customer["id"]
            db_execute(
                """
                UPDATE customers
                SET full_name=%s, email=%s, id_number=%s,
                    nationality=%s, address=%s
                WHERE id=%s
                """,
                (
                    guest.strip(),
                    email.strip(),
                    id_number.strip(),
                    nationality.strip(),
                    address.strip(),
                    customer_id,
                ),
            )
        else:
            customer_id = db_insert_return_id(
                """
                INSERT INTO customers
                (customer_code, full_name, phone, email, id_number,
                 nationality, address, note)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    make_code("KH"),
                    guest.strip(),
                    phone.strip(),
                    email.strip(),
                    id_number.strip(),
                    nationality.strip(),
                    address.strip(),
                    note.strip(),
                ),
            )

        if customer_id is None:
            st.error("Không tạo được thông tin khách hàng.")
            st.stop()

        # Kiểm tra lại tránh đặt trùng do thao tác đồng thời.
        conflict = db_fetch_one(
            """
            SELECT id
            FROM bookings
            WHERE room_number=%s
              AND status IN ('Đã đặt', 'Đang ở')
              AND check_in < %s
              AND check_out > %s
            LIMIT 1
            """,
            (room, check_out, check_in),
        )

        if conflict:
            st.error("Phòng vừa được đặt bởi người khác. Hãy chọn phòng khác.")
            st.stop()

        booking_code = make_code("BOOK")

        booking_id = db_insert_return_id(
            """
            INSERT INTO bookings
            (
                booking_code, customer_id, room_number,
                customer_name, phone, guests,
                check_in, check_out, nights,
                room_total, service_total, discount,
                grand_total, status, note
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,%s,'Đã đặt',%s)
            """,
            (
                booking_code,
                customer_id,
                room,
                guest.strip(),
                phone.strip(),
                guests,
                check_in,
                check_out,
                nights,
                room_total,
                room_total,
                note.strip(),
            ),
        )

        if booking_id:
            db_execute(
                """
                UPDATE rooms
                SET status='Đã đặt'
                WHERE room_number=%s
                """,
                (room,),
            )

            st.success(
                f"Đặt phòng thành công! Mã đặt phòng: {booking_code}"
            )
            st.rerun()


# =========================================================
# 15. CHECK-IN
# =========================================================

elif menu == "🛎️ Check-in":
    st.title("🛎️ Check-in")

    bookings = pd.DataFrame(
        db_fetch("""
            SELECT b.*, r.room_type, r.capacity
            FROM bookings b
            LEFT JOIN rooms r ON r.room_number=b.room_number
            WHERE b.status='Đã đặt'
            ORDER BY b.check_in, b.id
        """)
    )

    if bookings.empty:
        st.info("Hiện không có booking đang chờ check-in.")
    else:
        options = bookings["booking_code"].tolist()
        selected_code = st.selectbox("Chọn mã đặt phòng", options)

        selected = bookings[
            bookings["booking_code"] == selected_code
        ].iloc[0]

        c1, c2, c3 = st.columns(3)
        c1.metric("Khách", selected["customer_name"])
        c2.metric("Phòng", selected["room_number"])
        c3.metric("Số đêm", int(selected["nights"]))

        st.write(
            f"Ngày nhận phòng dự kiến: **{selected['check_in']}**"
        )
        st.write(
            f"Ngày trả phòng dự kiến: **{selected['check_out']}**"
        )
        st.write(f"Tiền phòng: **{money(selected['room_total'])}**")

        if st.button("🛎️ XÁC NHẬN CHECK-IN", use_container_width=True):
            room_status = db_fetch_one(
                "SELECT status FROM rooms WHERE room_number=%s",
                (selected["room_number"],),
            )

            if not room_status:
                st.error("Không tìm thấy phòng.")
            elif room_status["status"] == "Bảo trì":
                st.error("Phòng đang bảo trì, không thể check-in.")
            elif room_status["status"] == "Đang ở":
                st.error("Phòng đang có khách.")
            else:
                ok1 = db_execute(
                    """
                    UPDATE bookings
                    SET status='Đang ở', actual_check_in=NOW()
                    WHERE id=%s AND status='Đã đặt'
                    """,
                    (int(selected["id"]),),
                )
                ok2 = db_execute(
                    """
                    UPDATE rooms SET status='Đang ở'
                    WHERE room_number=%s
                    """,
                    (selected["room_number"],),
                )

                if ok1 and ok2:
                    st.success(
                        f"Check-in thành công cho {selected['customer_name']} - "
                        f"phòng {selected['room_number']}."
                    )
                    st.rerun()


# =========================================================
# 16. CHECK-OUT
# =========================================================

elif menu == "🚪 Check-out":
    st.title("🚪 Check-out")

    bookings = pd.DataFrame(
        db_fetch("""
            SELECT b.*, r.room_type
            FROM bookings b
            LEFT JOIN rooms r ON r.room_number=b.room_number
            WHERE b.status='Đang ở'
            ORDER BY b.actual_check_in DESC
        """)
    )

    if bookings.empty:
        st.info("Hiện không có khách đang ở.")
    else:
        selected_code = st.selectbox(
            "Chọn booking",
            bookings["booking_code"].tolist(),
        )

        selected = bookings[
            bookings["booking_code"] == selected_code
        ].iloc[0]

        # Dịch vụ đã dùng.
        service_rows = db_fetch(
            """
            SELECT bs.*, s.code, s.name, s.category
            FROM booking_services bs
            JOIN services s ON s.id=bs.service_id
            WHERE bs.booking_id=%s
            ORDER BY bs.id
            """,
            (int(selected["id"]),),
        )

        service_total = sum(
            safe_int(row["total"]) for row in service_rows
        )
        room_total = safe_int(selected["room_total"])
        discount = safe_int(selected["discount"])
        grand_total = room_total + service_total - discount

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Phòng", selected["room_number"])
        c2.metric("Tiền phòng", money(room_total))
        c3.metric("Dịch vụ", money(service_total))
        c4.metric("Tổng", money(grand_total))

        if service_rows:
            st.subheader("Dịch vụ đã sử dụng")
            service_df = pd.DataFrame(service_rows)
            st.dataframe(
                service_df[
                    ["code", "name", "quantity", "unit_price", "total"]
                ].rename(
                    columns={
                        "code": "Mã",
                        "name": "Dịch vụ",
                        "quantity": "SL",
                        "unit_price": "Đơn giá",
                        "total": "Thành tiền",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()

        if st.button("🚪 XÁC NHẬN CHECK-OUT", use_container_width=True):
            ok1 = db_execute(
                """
                UPDATE bookings
                SET status='Đã trả phòng',
                    actual_check_out=NOW(),
                    service_total=%s,
                    grand_total=%s
                WHERE id=%s AND status='Đang ở'
                """,
                (service_total, grand_total, int(selected["id"])),
            )

            ok2 = db_execute(
                """
                UPDATE rooms
                SET status='Đang dọn'
                WHERE room_number=%s
                """,
                (selected["room_number"],),
            )

            if ok1 and ok2:
                invoice_code = make_code("INV")
                db_execute(
                    """
                    INSERT INTO invoices
                    (
                        invoice_code, booking_id,
                        room_total, service_total,
                        discount, grand_total,
                        payment_method, payment_status
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,'Tiền mặt','Chưa thanh toán')
                    """,
                    (
                        invoice_code,
                        int(selected["id"]),
                        room_total,
                        service_total,
                        discount,
                        grand_total,
                    ),
                )

                st.success(
                    f"Check-out thành công. Mã hóa đơn: {invoice_code}. "
                    f"Phòng chuyển sang trạng thái Đang dọn."
                )
                st.rerun()


# =========================================================
# 17. KHÁCH HÀNG
# =========================================================

elif menu == "👥 Khách hàng":
    st.title("👥 Quản lý khách hàng")

    tab1, tab2 = st.tabs(["Danh sách khách", "Thêm khách"])

    with tab1:
        keyword = st.text_input(
            "Tìm theo tên / số điện thoại / CCCD",
            key="customer_search",
        )

        if keyword.strip():
            customers = db_fetch(
                """
                SELECT *
                FROM customers
                WHERE full_name LIKE %s
                   OR phone LIKE %s
                   OR id_number LIKE %s
                ORDER BY id DESC
                """,
                (
                    f"%{keyword.strip()}%",
                    f"%{keyword.strip()}%",
                    f"%{keyword.strip()}%",
                ),
            )
        else:
            customers = db_fetch("""
                SELECT *
                FROM customers
                ORDER BY id DESC
            """)

        customer_df = pd.DataFrame(customers)

        if customer_df.empty:
            st.info("Chưa có khách hàng.")
        else:
            display = customer_df.rename(
                columns={
                    "customer_code": "Mã khách",
                    "full_name": "Họ tên",
                    "phone": "Điện thoại",
                    "email": "Email",
                    "id_number": "CCCD/Hộ chiếu",
                    "nationality": "Quốc tịch",
                    "address": "Địa chỉ",
                }
            )
            columns = [
                c for c in [
                    "Mã khách",
                    "Họ tên",
                    "Điện thoại",
                    "Email",
                    "CCCD/Hộ chiếu",
                    "Quốc tịch",
                    "Địa chỉ",
                ] if c in display.columns
            ]
            st.dataframe(
                display[columns],
                use_container_width=True,
                hide_index=True,
            )

    with tab2:
        with st.form("add_customer"):
            full_name = st.text_input("Họ tên *")
            phone = st.text_input("Số điện thoại *")
            email = st.text_input("Email")
            id_number = st.text_input("CCCD/Hộ chiếu")
            nationality = st.text_input("Quốc tịch")
            address = st.text_input("Địa chỉ")
            note = st.text_area("Ghi chú")

            submit = st.form_submit_button(
                "THÊM KHÁCH HÀNG",
                use_container_width=True,
            )

        if submit:
            if not full_name.strip() or not phone.strip():
                st.warning("Vui lòng nhập họ tên và số điện thoại.")
            else:
                exists = db_fetch_one(
                    "SELECT id FROM customers WHERE phone=%s LIMIT 1",
                    (phone.strip(),),
                )
                if exists:
                    st.warning("Số điện thoại này đã tồn tại.")
                else:
                    new_id = db_insert_return_id(
                        """
                        INSERT INTO customers
                        (
                            customer_code, full_name, phone, email,
                            id_number, nationality, address, note
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            make_code("KH"),
                            full_name.strip(),
                            phone.strip(),
                            email.strip(),
                            id_number.strip(),
                            nationality.strip(),
                            address.strip(),
                            note.strip(),
                        ),
                    )
                    if new_id:
                        st.success("Đã thêm khách hàng.")
                        st.rerun()


# =========================================================
# 18. DỊCH VỤ
# =========================================================

elif menu == "🍽️ Dịch vụ":
    st.title("🍽️ Quản lý dịch vụ")

    tab1, tab2 = st.tabs(["Danh sách dịch vụ", "Thêm dịch vụ"])

    services = db_fetch("""
        SELECT id, code, name, category, price, active
        FROM services
        ORDER BY id
    """)

    service_df = pd.DataFrame(services)

    with tab1:
        if service_df.empty:
            st.info("Chưa có dịch vụ.")
        else:
            display = service_df.copy()
            display["active"] = display["active"].map(
                {1: "Đang hoạt động", 0: "Ngừng hoạt động"}
            )
            display = display.rename(
                columns={
                    "code": "Mã",
                    "name": "Dịch vụ",
                    "category": "Nhóm",
                    "price": "Giá",
                    "active": "Trạng thái",
                }
            )
            st.dataframe(
                display[["Mã", "Dịch vụ", "Nhóm", "Giá", "Trạng thái"]],
                use_container_width=True,
                hide_index=True,
            )

    with tab2:
        with st.form("add_service"):
            code = st.text_input("Mã dịch vụ *")
            name = st.text_input("Tên dịch vụ *")
            category = st.text_input("Nhóm dịch vụ", value="Khác")
            price = st.number_input(
                "Giá",
                min_value=0,
                value=100000,
                step=10000,
            )

            submit = st.form_submit_button(
                "THÊM DỊCH VỤ",
                use_container_width=True,
            )

        if submit:
            if not code.strip() or not name.strip():
                st.warning("Vui lòng nhập mã và tên dịch vụ.")
            else:
                ok = db_execute(
                    """
                    INSERT INTO services
                    (code, name, category, price, active)
                    VALUES (%s,%s,%s,%s,1)
                    """,
                    (
                        code.strip(),
                        name.strip(),
                        category.strip(),
                        price,
                    ),
                )
                if ok:
                    st.success("Đã thêm dịch vụ.")
                    st.rerun()

    st.divider()
    st.subheader("Thêm dịch vụ vào booking đang ở")

    active_bookings = db_fetch("""
        SELECT id, booking_code, room_number, customer_name
        FROM bookings
        WHERE status='Đang ở'
        ORDER BY actual_check_in DESC
    """)

    active_services = [
        s for s in services if int(s["active"]) == 1
    ]

    if not active_bookings:
        st.info("Chưa có khách đang ở để thêm dịch vụ.")
    elif not active_services:
        st.info("Chưa có dịch vụ hoạt động.")
    else:
        booking_map = {
            f'{b["booking_code"]} - Phòng {b["room_number"]} - {b["customer_name"]}':
                b["id"]
            for b in active_bookings
        }
        service_map = {
            f'{s["code"]} - {s["name"]} ({money(s["price"])})':
                s
            for s in active_services
        }

        with st.form("add_booking_service"):
            booking_label = st.selectbox(
                "Booking",
                list(booking_map.keys()),
            )
            service_label = st.selectbox(
                "Dịch vụ",
                list(service_map.keys()),
            )
            quantity = st.number_input(
                "Số lượng",
                min_value=1,
                max_value=100,
                value=1,
            )

            submit_service = st.form_submit_button(
                "THÊM VÀO BOOKING",
                use_container_width=True,
            )

        if submit_service:
            booking_id = booking_map[booking_label]
            service = service_map[service_label]

            ok = db_execute(
                """
                INSERT INTO booking_services
                (booking_id, service_id, quantity, unit_price, total)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    booking_id,
                    service["id"],
                    quantity,
                    service["price"],
                    int(service["price"]) * int(quantity),
                ),
            )

            if ok:
                # Cập nhật tổng dịch vụ và tổng booking.
                totals = db_fetch_one(
                    """
                    SELECT
                        COALESCE(SUM(total),0) AS service_total
                    FROM booking_services
                    WHERE booking_id=%s
                    """,
                    (booking_id,),
                )
                service_total = safe_int(totals["service_total"])

                booking = db_fetch_one(
                    """
                    SELECT room_total, discount
                    FROM bookings
                    WHERE id=%s
                    """,
                    (booking_id,),
                )

                grand_total = (
                    safe_int(booking["room_total"])
                    + service_total
                    - safe_int(booking["discount"])
                )

                db_execute(
                    """
                    UPDATE bookings
                    SET service_total=%s, grand_total=%s
                    WHERE id=%s
                    """,
                    (service_total, grand_total, booking_id),
                )

                st.success("Đã thêm dịch vụ vào booking.")
                st.rerun()


# =========================================================
# 19. HÓA ĐƠN
# =========================================================

elif menu == "🧾 Hóa đơn":
    st.title("🧾 Quản lý hóa đơn")

    invoices = pd.DataFrame(
        db_fetch("""
            SELECT
                i.id,
                i.invoice_code,
                i.booking_id,
                b.booking_code,
                b.customer_name,
                b.room_number,
                i.room_total,
                i.service_total,
                i.discount,
                i.grand_total,
                i.payment_method,
                i.payment_status,
                i.paid_at,
                i.created_at
            FROM invoices i
            JOIN bookings b ON b.id=i.booking_id
            ORDER BY i.id DESC
        """)
    )

    if invoices.empty:
        st.info("Chưa có hóa đơn.")
    else:
        display = invoices.rename(
            columns={
                "invoice_code": "Mã hóa đơn",
                "booking_code": "Booking",
                "customer_name": "Khách",
                "room_number": "Phòng",
                "room_total": "Tiền phòng",
                "service_total": "Dịch vụ",
                "discount": "Giảm giá",
                "grand_total": "Tổng tiền",
                "payment_method": "Thanh toán",
                "payment_status": "Trạng thái",
                "paid_at": "Đã thanh toán lúc",
                "created_at": "Ngày tạo",
            }
        )

        st.dataframe(
            display[
                [
                    "Mã hóa đơn",
                    "Booking",
                    "Khách",
                    "Phòng",
                    "Tiền phòng",
                    "Dịch vụ",
                    "Giảm giá",
                    "Tổng tiền",
                    "Thanh toán",
                    "Trạng thái",
                    "Đã thanh toán lúc",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("Thanh toán hóa đơn")

        unpaid = invoices[
            invoices["payment_status"] == "Chưa thanh toán"
        ]

        if unpaid.empty:
            st.success("Không có hóa đơn chưa thanh toán.")
        else:
            invoice_code = st.selectbox(
                "Chọn hóa đơn",
                unpaid["invoice_code"].tolist(),
            )

            selected = unpaid[
                unpaid["invoice_code"] == invoice_code
            ].iloc[0]

            st.info(
                f"Khách: {selected['customer_name']} | "
                f"Phòng: {selected['room_number']} | "
                f"Tổng: {money(selected['grand_total'])}"
            )

            payment_method = st.selectbox(
                "Phương thức thanh toán",
                ["Tiền mặt", "Chuyển khoản", "Thẻ", "Ví điện tử"],
            )

            if st.button("💳 XÁC NHẬN THANH TOÁN", use_container_width=True):
                ok = db_execute(
                    """
                    UPDATE invoices
                    SET payment_method=%s,
                        payment_status='Đã thanh toán',
                        paid_at=NOW()
                    WHERE invoice_code=%s
                    """,
                    (payment_method, invoice_code),
                )

                if ok:
                    st.success("Thanh toán thành công.")
                    st.rerun()


# =========================================================
# 20. DOANH THU
# =========================================================

elif menu == "💰 Doanh thu":
    st.title("💰 Doanh thu")

    c1, c2 = st.columns(2)

    with c1:
        from_date = st.date_input(
            "Từ ngày",
            date.today().replace(day=1),
        )

    with c2:
        to_date = st.date_input(
            "Đến ngày",
            date.today(),
        )

    if to_date < from_date:
        st.error("Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.")
        st.stop()

    revenue_rows = db_fetch(
        """
        SELECT
            DATE(COALESCE(i.paid_at, i.created_at)) AS revenue_date,
            COUNT(*) AS invoice_count,
            COALESCE(SUM(i.room_total),0) AS room_revenue,
            COALESCE(SUM(i.service_total),0) AS service_revenue,
            COALESCE(SUM(i.discount),0) AS discount_total,
            COALESCE(SUM(i.grand_total),0) AS total_revenue
        FROM invoices i
        WHERE i.payment_status='Đã thanh toán'
          AND DATE(COALESCE(i.paid_at, i.created_at))
              BETWEEN %s AND %s
        GROUP BY DATE(COALESCE(i.paid_at, i.created_at))
        ORDER BY revenue_date
        """,
        (from_date, to_date),
    )

    revenue_df = pd.DataFrame(revenue_rows)

    total_revenue = (
        revenue_df["total_revenue"].sum()
        if not revenue_df.empty else 0
    )
    room_revenue = (
        revenue_df["room_revenue"].sum()
        if not revenue_df.empty else 0
    )
    service_revenue = (
        revenue_df["service_revenue"].sum()
        if not revenue_df.empty else 0
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Tổng doanh thu", money(total_revenue))
    m2.metric("Doanh thu phòng", money(room_revenue))
    m3.metric("Doanh thu dịch vụ", money(service_revenue))

    if revenue_df.empty:
        st.info("Chưa có dữ liệu doanh thu trong khoảng thời gian này.")
    else:
        display = revenue_df.rename(
            columns={
                "revenue_date": "Ngày",
                "invoice_count": "Số hóa đơn",
                "room_revenue": "Doanh thu phòng",
                "service_revenue": "Doanh thu dịch vụ",
                "discount_total": "Giảm giá",
                "total_revenue": "Tổng doanh thu",
            }
        )
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
        )

        chart_df = revenue_df.copy()
        chart_df["revenue_date"] = pd.to_datetime(
            chart_df["revenue_date"]
        )
        chart_df = chart_df.set_index("revenue_date")
        st.line_chart(chart_df["total_revenue"])


# =========================================================
# 21. CHAT
# =========================================================

elif menu == "💬 Chat với khách":
    st.title("💬 Chat với khách")

    messages = db_fetch("""
        SELECT sender, customer_name, message, created_at
        FROM chat_messages
        ORDER BY id DESC
        LIMIT 100
    """)

    if messages:
        for msg in reversed(messages):
            sender = msg["sender"]
            name = msg["customer_name"] or "Khách"
            css_class = "chat-user" if sender == "customer" else "chat-hotel"
            label = "👤" if sender == "customer" else "🏨"

            st.markdown(
                f"""
                <div style="
                    background:{'#dff3ff' if sender == 'customer' else '#f0f3f4'};
                    padding:12px;
                    border-radius:12px;
                    margin:7px 0;
                ">
                    <b>{label} {name}</b><br>
                    {msg["message"]}<br>
                    <span class="small-muted">{msg["created_at"]}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("Chưa có tin nhắn.")

    st.divider()

    with st.form("chat_form"):
        customer_name = st.text_input(
            "Tên khách",
            value="Khách",
        )
        message = st.text_area("Nội dung")
        sender = st.selectbox(
            "Người gửi",
            ["hotel", "customer"],
            format_func=lambda x: "Khách sạn" if x == "hotel" else "Khách",
        )
        submit = st.form_submit_button(
            "GỬI TIN NHẮN",
            use_container_width=True,
        )

    if submit:
        if not message.strip():
            st.warning("Vui lòng nhập nội dung.")
        else:
            ok = db_execute(
                """
                INSERT INTO chat_messages
                (sender, customer_name, message)
                VALUES (%s,%s,%s)
                """,
                (
                    sender,
                    customer_name.strip(),
                    message.strip(),
                ),
            )
            if ok:
                st.success("Đã gửi.")
                st.rerun()


# =========================================================
# 22. BÁO CÁO
# =========================================================

elif menu == "📊 Báo cáo":
    st.title("📊 Báo cáo quản lý khách sạn")

    rooms = pd.DataFrame(
        db_fetch("""
            SELECT floor, room_type, status, price
            FROM rooms
        """)
    )

    bookings = pd.DataFrame(
        db_fetch("""
            SELECT
                booking_code, room_number, customer_name,
                check_in, check_out, nights,
                room_total, service_total, grand_total, status
            FROM bookings
            ORDER BY id DESC
        """)
    )

    if not rooms.empty:
        st.subheader("Tình trạng phòng")

        status_report = (
            rooms.groupby("status")
            .size()
            .reset_index(name="Số phòng")
        )

        st.dataframe(
            status_report,
            use_container_width=True,
            hide_index=True,
        )

        st.bar_chart(
            status_report.set_index("status")["Số phòng"]
        )

        st.subheader("Phòng theo hạng")

        type_report = (
            rooms.groupby("room_type")
            .size()
            .reset_index(name="Số phòng")
        )

        st.dataframe(
            type_report,
            use_container_width=True,
            hide_index=True,
        )

    if not bookings.empty:
        st.subheader("Tổng hợp booking")

        booking_report = (
            bookings.groupby("status")
            .agg(
                so_booking=("booking_code", "count"),
                tong_tien=("grand_total", "sum"),
            )
            .reset_index()
        )

        booking_report = booking_report.rename(
            columns={
                "status": "Trạng thái",
                "so_booking": "Số booking",
                "tong_tien": "Tổng tiền",
            }
        )

        st.dataframe(
            booking_report,
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Danh sách booking gần đây")

        booking_display = bookings.rename(
            columns={
                "booking_code": "Mã booking",
                "room_number": "Phòng",
                "customer_name": "Khách",
                "check_in": "Check-in",
                "check_out": "Check-out",
                "nights": "Đêm",
                "room_total": "Tiền phòng",
                "service_total": "Dịch vụ",
                "grand_total": "Tổng",
                "status": "Trạng thái",
            }
        )

        st.dataframe(
            booking_display[
                [
                    "Mã booking",
                    "Phòng",
                    "Khách",
                    "Check-in",
                    "Check-out",
                    "Đêm",
                    "Tiền phòng",
                    "Dịch vụ",
                    "Tổng",
                    "Trạng thái",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

# =========================================================
# 23. FOOTER
# =========================================================

st.divider()
st.caption(
    f"{HOTEL_NAME} · {LOCATION} · Hotel Management System · "
    f"MySQL Aiven"
)
