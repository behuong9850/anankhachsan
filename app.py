import streamlit as st
import pandas as pd
import pymysql
from pymysql.cursors import DictCursor
from datetime import date, datetime, timedelta
from pathlib import Path
import html
import base64
import time

# ============================================================
# CHARM PEARL HOTEL - STREAMLIT + MYSQL AIVEN
# ============================================================
# Lưu ý:
# - Database: Aiven MySQL
# - Host/Port/User/Database lấy theo thông tin Aiven bạn cung cấp.
# - Password đang đặt là 123 theo thông tin bạn đã cung cấp trước đó.
# - Nếu password Aiven thực tế khác 123, chỉ sửa MYSQL_PASSWORD.
# ============================================================

st.set_page_config(
    page_title="Charm Pearl Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE = Path(__file__).parent

HOTEL_NAME = "CHARM PEARL HOTEL"
LOCATION = "VŨNG TÀU"

# ============================================================
# 1. THÔNG TIN MYSQL AIVEN
# ============================================================

MYSQL_HOST = "huong-nguyen-jnnxjany005-da5d.i.aivencloud.com"
MYSQL_PORT = 28463
MYSQL_USER = "avnadmin"
MYSQL_PASSWORD = "AVNS_Y-9KXwC_DRlZtoJdTOY"
MYSQL_DATABASE = "defaultdb"

# Aiven yêu cầu SSL. Nếu bạn có CA certificate, đặt đường dẫn vào đây.
# Ví dụ: AIVEN_CA = BASE / "ca.pem"
AIVEN_CA = None


# ============================================================
# 2. CẤU HÌNH HẠNG PHÒNG
# ============================================================

ROOM_TYPES = {
    "Deluxe Room King": {
        "price": 850000,
        "capacity": 2,
        "beds": "1 giường King",
        "description": "Phòng nghỉ hiện đại dành cho 1–2 khách.",
    },
    "Deluxe Room Twins": {
        "price": 850000,
        "capacity": 2,
        "beds": "2 giường đơn",
        "description": "Phù hợp cho bạn bè hoặc khách công tác.",
    },
    "Premier Garden": {
        "price": 1100000,
        "capacity": 2,
        "beds": "1 giường King",
        "description": "Không gian nghỉ dưỡng hướng vườn.",
    },
    "Premier Ocean": {
        "price": 1350000,
        "capacity": 2,
        "beds": "1 giường King",
        "description": "Phòng cao cấp với không gian hướng biển.",
    },
    "Princess Suite": {
        "price": 1800000,
        "capacity": 3,
        "beds": "1 giường King",
        "description": "Suite rộng rãi dành cho kỳ nghỉ cao cấp.",
    },
    "Royal Suite Villa": {
        "price": 3000000,
        "capacity": 6,
        "beds": "King + giường phụ",
        "description": "Villa cao cấp dành cho gia đình hoặc nhóm khách.",
    },
}

# ============================================================
# 2B. HÌNH ẢNH KHÁCH SẠN
# ============================================================
LOGO = BASE / "IMG_LOGO1.jpg"
BANNER = BASE / "IMG_BANNER2.jpg"
BACKGROUND = BASE / "IMG_NENCHIM3.jpg"

ROOM_IMAGES = {
    "Deluxe Room King": ["IMG_DELUXEKING.jpg", "IMG_DELUXEKING1.jpg", "IMG_DELUXEROOMKING.jpg", "DELUXEKING.jpg"],
    "Deluxe Room Twins": ["IMG_DELUXETWINS.jpg", "IMG_DELUXETWINS1.jpg", "IMG_DELUXEROOMTWINS.jpg", "DELUXETWINS.jpg"],
    "Premier Garden": ["IMG_PREMIERGARDEN.jpg", "IMG_PREMIERGARDEN1.jpg", "PREMIERGARDEN.jpg"],
    "Premier Ocean": ["IMG_PREMIEROCEAN.jpg", "IMG_PREMIEROCEAN1.jpg", "PREMIEROCEAN.jpg"],
    "Princess Suite": ["IMG_PRINCESSSUITE.jpg", "IMG_PRINCESSSUITE1.jpg", "PRINCESSSUITE.jpg"],
    "Royal Suite Villa": ["IMG_ROYALSUITEVILLA.jpg", "IMG_ROYALSUITEVILLA1.jpg", "ROYALSUITEVILLA.jpg"],
}

def find_room_image(room_type):
    for filename in ROOM_IMAGES.get(room_type, []):
        path = BASE / filename
        if path.exists():
            return path
    return None


STATUSES = ["Trống", "Đã đặt", "Đang ở", "Đang dọn", "Bảo trì"]

BOOKING_STATUSES = ["Đã đặt", "Đang ở", "Đã trả phòng", "Hủy"]

PAYMENT_METHODS = [
    "Tiền mặt",
    "Chuyển khoản",
    "Thẻ tín dụng",
    "Ví điện tử",
]


# ============================================================
# 3. TIỆN ÍCH
# ============================================================

def money(value):
    try:
        return f"{int(float(value or 0)):,.0f}".replace(",", ".") + " VNĐ"
    except Exception:
        return "0 VNĐ"


def status_icon(status):
    return {
        "Trống": "🟢",
        "Đã đặt": "🟣",
        "Đang ở": "🔵",
        "Đang dọn": "🟡",
        "Bảo trì": "🔴",
    }.get(status, "⚪")


def safe(value):
    return html.escape(str(value if value is not None else ""))


def file_to_base64(path):
    try:
        path = Path(path)
        if not path.exists():
            return None
        return base64.b64encode(path.read_bytes()).decode()
    except Exception:
        return None


# ============================================================
# 4. KẾT NỐI MYSQL AIVEN
# ============================================================

def get_connection():
    ssl_args = {
        "check_hostname": False,
    }

    if AIVEN_CA and Path(AIVEN_CA).exists():
        ssl_args["ca"] = str(AIVEN_CA)

    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        connect_timeout=20,
        read_timeout=30,
        write_timeout=30,
        ssl=ssl_args,
    )


def reset_db_connection():
    # Connection không được cache; mỗi thao tác DB dùng một connection riêng.
    return None


def db_query(sql, params=None, fetch=True):
    """
    Chạy SELECT bằng connection mới.
    Connection luôn được đóng sau khi đọc xong dữ liệu.
    """
    for attempt in range(2):
        conn = None
        try:
            conn = get_connection()
            conn.ping(reconnect=True)

            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                if fetch:
                    return cursor.fetchall()

            return []

        except Exception as exc:
            if attempt == 0:
                time.sleep(0.3)
            else:
                st.error(f"Lỗi MySQL: {exc}")
                return []

        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


def db_execute(sql, params=None):
    """
    Chạy INSERT/UPDATE/DELETE bằng connection mới.
    Commit xong luôn đóng connection.
    """
    for attempt in range(2):
        conn = None
        try:
            conn = get_connection()
            conn.ping(reconnect=True)

            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                rowcount = cursor.rowcount

            conn.commit()
            return rowcount

        except Exception as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass

            if attempt == 0:
                time.sleep(0.3)
            else:
                st.error(f"Lỗi MySQL: {exc}")
                return 0

        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


# ============================================================
# 5. KHỞI TẠO DATABASE
# ============================================================

def initialize_database():
    conn = None

    try:
        conn = get_connection()
        conn.ping(reconnect=True)

        with conn.cursor() as cursor:
            # ---------------- ROOMS ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    room_number VARCHAR(10) NOT NULL UNIQUE,
                    floor INT NOT NULL,
                    room_type VARCHAR(100) NOT NULL,
                    price BIGINT NOT NULL,
                    capacity INT NOT NULL,
                    status VARCHAR(30) NOT NULL DEFAULT 'Trống',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_rooms_status (status),
                    INDEX idx_rooms_type (room_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # ---------------- GUESTS ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS guests (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(150) NOT NULL,
                    phone VARCHAR(30),
                    email VARCHAR(150),
                    id_number VARCHAR(50),
                    address VARCHAR(255),
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_guests_name (full_name),
                    INDEX idx_guests_phone (phone),
                    INDEX idx_guests_id_number (id_number)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # ---------------- BOOKINGS ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    booking_code VARCHAR(40) NOT NULL UNIQUE,
                    guest_id INT NOT NULL,
                    room_id INT NOT NULL,
                    room_number VARCHAR(10) NOT NULL,
                    customer_name VARCHAR(150) NOT NULL,
                    phone VARCHAR(30),
                    email VARCHAR(150),
                    guests INT DEFAULT 1,
                    adults INT DEFAULT 1,
                    children INT DEFAULT 0,
                    check_in DATE NOT NULL,
                    check_out DATE NOT NULL,
                    nights INT NOT NULL,
                    room_price BIGINT NOT NULL,
                    room_total BIGINT NOT NULL,
                    service_total BIGINT NOT NULL DEFAULT 0,
                    grand_total BIGINT NOT NULL DEFAULT 0,
                    paid_amount BIGINT NOT NULL DEFAULT 0,
                    status VARCHAR(50) NOT NULL DEFAULT 'Đã đặt',
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guest_id) REFERENCES guests(id),
                    FOREIGN KEY (room_id) REFERENCES rooms(id),
                    INDEX idx_booking_dates (check_in, check_out),
                    INDEX idx_booking_room (room_id),
                    INDEX idx_booking_status (status),
                    INDEX idx_booking_code (booking_code)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # ---------------- SERVICES ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(30) NOT NULL UNIQUE,
                    name VARCHAR(150) NOT NULL,
                    price BIGINT NOT NULL DEFAULT 0,
                    active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # ---------------- BOOKING SERVICES ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS booking_services (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    booking_id INT NOT NULL,
                    service_id INT NOT NULL,
                    quantity INT NOT NULL DEFAULT 1,
                    unit_price BIGINT NOT NULL,
                    total_price BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
                    FOREIGN KEY (service_id) REFERENCES services(id),
                    INDEX idx_bs_booking (booking_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # ---------------- PAYMENTS ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    booking_id INT NOT NULL,
                    amount BIGINT NOT NULL,
                    payment_method VARCHAR(50) NOT NULL,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
                    INDEX idx_payments_booking (booking_id),
                    INDEX idx_payments_date (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # ---------------- CHAT ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    sender VARCHAR(30) NOT NULL,
                    customer_name VARCHAR(100) DEFAULT 'Khách',
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_chat_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # ---------------- SEED ROOMS ----------------
            cursor.execute("SELECT COUNT(*) AS total FROM rooms")
            room_count = cursor.fetchone()["total"]

            if room_count == 0:
                room_rows = []

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

                        room_rows.append((
                            room_number,
                            floor,
                            room_type,
                            info["price"],
                            info["capacity"],
                            "Trống",
                        ))

                cursor.executemany("""
                    INSERT INTO rooms
                    (room_number, floor, room_type, price, capacity, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, room_rows)

            # ---------------- SEED SERVICES ----------------
            cursor.execute("SELECT COUNT(*) AS total FROM services")
            service_count = cursor.fetchone()["total"]

            if service_count == 0:
                service_rows = [
                    ("DV001", "Ăn sáng", 120000),
                    ("DV002", "Cà phê", 50000),
                    ("DV003", "Giặt ủi", 80000),
                    ("DV004", "Minibar", 100000),
                    ("DV005", "Extra Bed", 250000),
                    ("DV006", "Spa", 350000),
                    ("DV007", "Đưa đón sân bay", 400000),
                ]

                cursor.executemany("""
                    INSERT INTO services (code, name, price)
                    VALUES (%s, %s, %s)
                """, service_rows)

        conn.commit()
        return True, "MySQL Aiven đã sẵn sàng."

    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, str(exc)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# 6. DATA ACCESS
# ============================================================

def fetch_rooms():
    rows = db_query("""
        SELECT *
        FROM rooms
        ORDER BY floor, room_number
    """)
    return pd.DataFrame(rows)


def fetch_bookings():
    rows = db_query("""
        SELECT
            b.*,
            g.email,
            g.id_number,
            g.address,
            r.room_type,
            r.floor
        FROM bookings b
        LEFT JOIN guests g ON g.id = b.guest_id
        LEFT JOIN rooms r ON r.id = b.room_id
        ORDER BY b.id DESC
    """)
    return pd.DataFrame(rows)


def fetch_guests():
    rows = db_query("""
        SELECT *
        FROM guests
        ORDER BY id DESC
    """)
    return pd.DataFrame(rows)


def fetch_services():
    rows = db_query("""
        SELECT *
        FROM services
        ORDER BY active DESC, id
    """)
    return pd.DataFrame(rows)


def fetch_payments(booking_id=None):
    if booking_id:
        return pd.DataFrame(db_query("""
            SELECT *
            FROM payments
            WHERE booking_id=%s
            ORDER BY id DESC
        """, (booking_id,)))

    return pd.DataFrame(db_query("""
        SELECT
            p.*,
            b.booking_code,
            b.customer_name,
            b.room_number
        FROM payments p
        JOIN bookings b ON b.id=p.booking_id
        ORDER BY p.id DESC
    """))


def generate_booking_code():
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = str(int(time.time() * 1000))[-4:]
    return f"CPH-{stamp}-{suffix}"


# ============================================================
# 7. NGHIỆP VỤ PHÒNG
# ============================================================

def add_room(room_number, room_type, floor, price, capacity, status="Trống"):
    try:
        db_execute("""
            INSERT INTO rooms
            (room_number, room_type, floor, price, capacity, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            room_number.strip(),
            room_type,
            int(floor),
            int(price),
            int(capacity),
            status,
        ))
        return True, "Thêm phòng thành công."
    except Exception as exc:
        return False, f"Không thể thêm phòng: {exc}"


def update_room(room_id, room_number, room_type, floor, price, capacity, status):
    try:
        db_execute("""
            UPDATE rooms
            SET room_number=%s,
                room_type=%s,
                floor=%s,
                price=%s,
                capacity=%s,
                status=%s
            WHERE id=%s
        """, (
            room_number.strip(),
            room_type,
            int(floor),
            int(price),
            int(capacity),
            status,
            int(room_id),
        ))
        return True, "Cập nhật phòng thành công."
    except Exception as exc:
        return False, f"Không thể cập nhật phòng: {exc}"


def delete_room(room_id):
    rows = db_query("""
        SELECT COUNT(*) AS total
        FROM bookings
        WHERE room_id=%s
    """, (room_id,))

    if rows and rows[0]["total"] > 0:
        return False, "Không thể xóa phòng vì phòng đã có lịch sử đặt."

    db_execute("DELETE FROM rooms WHERE id=%s", (room_id,))
    return True, "Đã xóa phòng."


# ============================================================
# 8. ĐẶT PHÒNG - CÓ KIỂM TRA TRÙNG NGÀY
# ============================================================

def create_booking(
    full_name,
    phone,
    email,
    id_number,
    room_id,
    check_in,
    check_out,
    adults,
    children,
    note,
):
    if check_out <= check_in:
        return False, "Ngày trả phòng phải sau ngày nhận phòng."

    nights = (check_out - check_in).days

    conn = None

    try:
        conn = get_connection()
        conn.ping(reconnect=True)

        with conn.cursor() as cursor:
            # Khóa phòng trong transaction để hạn chế đặt trùng khi có
            # hai người cùng thao tác.
            cursor.execute("""
                SELECT *
                FROM rooms
                WHERE id=%s
                FOR UPDATE
            """, (room_id,))

            room = cursor.fetchone()

            if not room:
                raise ValueError("Không tìm thấy phòng.")

            if room["status"] == "Bảo trì":
                raise ValueError("Phòng đang bảo trì.")

            if int(adults) + int(children) > int(room["capacity"]):
                raise ValueError(
                    f"Phòng chỉ cho tối đa {room['capacity']} khách."
                )

            # Kiểm tra booking đang chiếm phòng trong khoảng ngày.
            cursor.execute("""
                SELECT id, booking_code
                FROM bookings
                WHERE room_id=%s
                  AND status NOT IN ('Hủy', 'Đã trả phòng')
                  AND check_in < %s
                  AND check_out > %s
                LIMIT 1
                FOR UPDATE
            """, (
                room_id,
                check_out,
                check_in,
            ))

            conflict = cursor.fetchone()

            if conflict:
                raise ValueError(
                    f"Phòng đã có booking {conflict['booking_code']} "
                    f"trùng khoảng ngày này."
                )

            # Tìm khách cũ theo CCCD hoặc số điện thoại.
            guest_id = None

            if id_number and id_number.strip():
                cursor.execute("""
                    SELECT id
                    FROM guests
                    WHERE id_number=%s
                    ORDER BY id DESC
                    LIMIT 1
                """, (id_number.strip(),))
                old_guest = cursor.fetchone()
                if old_guest:
                    guest_id = old_guest["id"]

            if guest_id is None and phone and phone.strip():
                cursor.execute("""
                    SELECT id
                    FROM guests
                    WHERE phone=%s
                    ORDER BY id DESC
                    LIMIT 1
                """, (phone.strip(),))
                old_guest = cursor.fetchone()
                if old_guest:
                    guest_id = old_guest["id"]

            if guest_id:
                cursor.execute("""
                    UPDATE guests
                    SET full_name=%s,
                        phone=%s,
                        email=%s,
                        id_number=%s
                    WHERE id=%s
                """, (
                    full_name.strip(),
                    phone.strip(),
                    email.strip(),
                    id_number.strip(),
                    guest_id,
                ))
            else:
                cursor.execute("""
                    INSERT INTO guests
                    (full_name, phone, email, id_number)
                    VALUES (%s, %s, %s, %s)
                """, (
                    full_name.strip(),
                    phone.strip(),
                    email.strip(),
                    id_number.strip(),
                ))
                guest_id = cursor.lastrowid

            room_total = nights * int(room["price"])
            booking_code = generate_booking_code()

            cursor.execute("""
                INSERT INTO bookings
                (
                    booking_code,
                    guest_id,
                    room_id,
                    room_number,
                    customer_name,
                    phone,
                    email,
                    guests,
                    adults,
                    children,
                    check_in,
                    check_out,
                    nights,
                    room_price,
                    room_total,
                    service_total,
                    grand_total,
                    paid_amount,
                    status,
                    note
                )
                VALUES
                (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,0,%s,0,'Đã đặt',%s
                )
            """, (
                booking_code,
                guest_id,
                room_id,
                room["room_number"],
                full_name.strip(),
                phone.strip(),
                email.strip(),
                int(adults) + int(children),
                int(adults),
                int(children),
                check_in,
                check_out,
                nights,
                int(room["price"]),
                room_total,
                room_total,
                note.strip(),
            ))

            cursor.execute("""
                UPDATE rooms
                SET status='Đã đặt'
                WHERE id=%s
            """, (room_id,))

        conn.commit()

        return True, (
            f"Đặt phòng thành công. "
            f"Mã booking: {booking_code}. "
            f"Tổng tiền: {money(room_total)}"
        )

    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, str(exc)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def update_booking_status(booking_id, new_status):
    conn = None

    try:
        conn = get_connection()
        conn.ping(reconnect=True)

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM bookings
                WHERE id=%s
                FOR UPDATE
            """, (booking_id,))
            booking = cursor.fetchone()

            if not booking:
                raise ValueError("Không tìm thấy booking.")

            room_id = booking["room_id"]

            cursor.execute("""
                UPDATE bookings
                SET status=%s
                WHERE id=%s
            """, (new_status, booking_id))

            if new_status == "Đã đặt":
                room_status = "Đã đặt"
            elif new_status == "Đang ở":
                room_status = "Đang ở"
            elif new_status == "Đã trả phòng":
                room_status = "Đang dọn"
            elif new_status == "Hủy":
                room_status = "Trống"
            else:
                room_status = "Trống"

            cursor.execute("""
                UPDATE rooms
                SET status=%s
                WHERE id=%s
            """, (room_status, room_id))

        conn.commit()
        return True, "Đã cập nhật trạng thái."

    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, str(exc)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# 9. THANH TOÁN
# ============================================================

def make_payment(booking_id, amount, method, note):
    amount = int(amount)

    if amount <= 0:
        return False, "Số tiền thanh toán phải lớn hơn 0."

    conn = None

    try:
        conn = get_connection()
        conn.ping(reconnect=True)

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM bookings
                WHERE id=%s
                FOR UPDATE
            """, (booking_id,))
            booking = cursor.fetchone()

            if not booking:
                raise ValueError("Không tìm thấy booking.")

            remaining = int(booking["grand_total"]) - int(booking["paid_amount"])

            if amount > remaining:
                raise ValueError(
                    f"Số tiền còn phải thanh toán chỉ là {money(remaining)}."
                )

            cursor.execute("""
                INSERT INTO payments
                (booking_id, amount, payment_method, note)
                VALUES (%s,%s,%s,%s)
            """, (
                booking_id,
                amount,
                method,
                note.strip(),
            ))

            cursor.execute("""
                UPDATE bookings
                SET paid_amount=paid_amount+%s
                WHERE id=%s
            """, (amount, booking_id))

        conn.commit()
        return True, "Thanh toán đã được ghi nhận."

    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, str(exc)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# 10. DỊCH VỤ
# ============================================================

def add_service(code, name, price):
    try:
        db_execute("""
            INSERT INTO services (code, name, price)
            VALUES (%s,%s,%s)
        """, (code.strip(), name.strip(), int(price)))
        return True, "Đã thêm dịch vụ."
    except Exception as exc:
        return False, str(exc)


def add_booking_service(booking_id, service_id, quantity):
    conn = None

    try:
        conn = get_connection()
        conn.ping(reconnect=True)

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM services
                WHERE id=%s AND active=1
            """, (service_id,))
            service = cursor.fetchone()

            if not service:
                raise ValueError("Dịch vụ không tồn tại.")

            total = int(service["price"]) * int(quantity)

            cursor.execute("""
                INSERT INTO booking_services
                (booking_id, service_id, quantity, unit_price, total_price)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                booking_id,
                service_id,
                int(quantity),
                int(service["price"]),
                total,
            ))

            cursor.execute("""
                SELECT COALESCE(SUM(total_price),0) AS service_total
                FROM booking_services
                WHERE booking_id=%s
            """, (booking_id,))
            service_total = int(cursor.fetchone()["service_total"])

            cursor.execute("""
                UPDATE bookings
                SET service_total=%s,
                    grand_total=room_total+%s
                WHERE id=%s
            """, (
                service_total,
                service_total,
                booking_id,
            ))

        conn.commit()
        return True, "Đã thêm dịch vụ vào booking."

    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, str(exc)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# 11. KHỞI TẠO
# ============================================================

db_ready, db_message = initialize_database()


# ============================================================
# 12. CSS
# ============================================================

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
    background: rgba(255,255,255,0.96);
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
}

.card {
    background: rgba(255,255,255,0.96);
    padding: 20px;
    border-radius: 16px;
    box-shadow: 0 3px 15px rgba(0,0,0,0.08);
}

.card-title {
    color: #71828a;
    font-size: 14px;
}

.card-number {
    color: #123d4d;
    font-size: 27px;
    font-weight: 800;
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

.chat-user {
    background: #dff3ff;
    padding: 12px;
    border-radius: 12px;
    margin: 7px 0;
}

.chat-hotel {
    background: #f0f3f4;
    padding: 12px;
    border-radius: 12px;
    margin: 7px 0;
}

.room-image-card {
    background: rgba(255,255,255,0.97);
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid #e2e8eb;
    box-shadow: 0 4px 16px rgba(0,0,0,0.07);
    margin-bottom: 20px;
}

.room-image-placeholder {
    height: 220px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #eaf1f4, #f7f9fa);
    color: #78909c;
    font-size: 46px;
}

.room-image-info {
    padding: 16px 18px 18px 18px;
}

.room-image-title {
    font-size: 20px;
    font-weight: 800;
    color: #123d4d;
    margin-bottom: 5px;
}

.asset-note {
    color: #71828a;
    font-size: 13px;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 12B. HÌNH ẢNH NỀN / LOGO / BANNER
# ============================================================

bg64 = file_to_base64(BACKGROUND)
if bg64:
    st.markdown(
        f"""<style>
        .stApp {{
            background-image: linear-gradient(rgba(247,250,251,0.94), rgba(247,250,251,0.94)),
                              url('data:image/jpeg;base64,{bg64}');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        </style>""",
        unsafe_allow_html=True,
    )


# ============================================================
# 13. SIDEBAR
# ============================================================

with st.sidebar:
    if LOGO.exists():
        st.image(str(LOGO), width=88)
    st.markdown("## 🏨 CHARM PEARL HOTEL")
    st.caption("HOTEL MANAGEMENT SYSTEM")
    st.caption("Vũng Tàu")

    if db_ready:
        st.success("MySQL Aiven: Đã kết nối")
    else:
        st.error("MySQL Aiven: Lỗi kết nối")

    st.divider()

    menu = st.radio(
        "MENU QUẢN LÝ",
        [
            "🏠 Dashboard",
            "🛏️ Quản lý phòng",
            "📷 Hạng phòng",
            "📅 Đặt phòng",
            "🛎️ Check-in / Check-out",
            "👥 Khách hàng",
            "🧴 Dịch vụ",
            "🧾 Hóa đơn",
            "💰 Doanh thu",
            "💬 Chat với khách",
            "📊 Báo cáo",
        ],
    )

    st.divider()
    st.caption("CHARM PEARL HOTEL")
    st.caption("50 phòng · 5 tầng")


if not db_ready:
    st.error(
        "Không thể kết nối MySQL Aiven. "
        f"Chi tiết: {db_message}"
    )
    st.code(
        f"""Host: {MYSQL_HOST}
Port: {MYSQL_PORT}
User: {MYSQL_USER}
Database: {MYSQL_DATABASE}
SSL: REQUIRED""",
        language="text",
    )
    st.stop()


# ============================================================
# 14. DASHBOARD
# ============================================================

if menu == "🏠 Dashboard":
    if BANNER.exists():
        left, center, right = st.columns([1, 2.5, 1])
        with center:
            st.image(str(BANNER), use_container_width=True)

    st.markdown("""
    <div class="hero">
        <div class="hero-title">CHARM PEARL HOTEL</div>
        <div class="hero-sub">Hotel Management System · Vũng Tàu</div>
    </div>
    """, unsafe_allow_html=True)

    rooms = fetch_rooms()
    bookings = fetch_bookings()

    total_rooms = len(rooms)
    empty_rooms = len(rooms[rooms["status"] == "Trống"]) if not rooms.empty else 0
    reserved_rooms = len(rooms[rooms["status"] == "Đã đặt"]) if not rooms.empty else 0
    occupied_rooms = len(rooms[rooms["status"] == "Đang ở"]) if not rooms.empty else 0
    cleaning_rooms = len(rooms[rooms["status"] == "Đang dọn"]) if not rooms.empty else 0
    maintenance_rooms = len(rooms[rooms["status"] == "Bảo trì"]) if not rooms.empty else 0

    revenue = int(bookings["paid_amount"].sum()) if not bookings.empty else 0

    cards = st.columns(6)
    data = [
        ("🏨", "Tổng phòng", total_rooms),
        ("🟢", "Phòng trống", empty_rooms),
        ("🟣", "Đã đặt", reserved_rooms),
        ("🔵", "Đang ở", occupied_rooms),
        ("🧹", "Đang dọn", cleaning_rooms),
        ("💰", "Đã thu", money(revenue)),
    ]

    for col, item in zip(cards, data):
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

    st.markdown('<div class="section-title">Sơ đồ phòng</div>', unsafe_allow_html=True)

    floor = st.selectbox(
        "Chọn tầng",
        ["Tất cả", 1, 2, 3, 4, 5],
        key="dashboard_floor",
    )

    show_rooms = rooms.copy()
    if not show_rooms.empty and floor != "Tất cả":
        show_rooms = show_rooms[show_rooms["floor"] == floor]

    if show_rooms.empty:
        st.info("Chưa có phòng.")
    else:
        cols = st.columns(5)

        for i, (_, room) in enumerate(show_rooms.iterrows()):
            with cols[i % 5]:
                st.markdown(
                    f"""
                    <div class="room-card">
                        <div class="room-number">🚪 {safe(room["room_number"])}</div>
                        <div class="room-type">
                            {safe(room["room_type"])} · Tầng {room["floor"]}
                        </div>
                        <p>{money(room["price"])} / đêm</p>
                        <b>{status_icon(room["status"])} {safe(room["status"])}</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.divider()
    st.subheader("📅 Booking gần đây")

    if bookings.empty:
        st.info("Chưa có booking.")
    else:
        show = bookings.head(10).copy()
        show["Tổng tiền"] = show["grand_total"].apply(money)
        show["Đã thanh toán"] = show["paid_amount"].apply(money)
        st.dataframe(
            show[
                [
                    "booking_code",
                    "customer_name",
                    "room_number",
                    "check_in",
                    "check_out",
                    "status",
                    "Tổng tiền",
                    "Đã thanh toán",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# 15. QUẢN LÝ PHÒNG
# ============================================================

elif menu == "🛏️ Quản lý phòng":
    st.title("🛏️ Quản lý phòng")

    rooms = fetch_rooms()

    tab1, tab2, tab3 = st.tabs(
        ["Danh sách phòng", "➕ Thêm phòng", "✏️ Chỉnh sửa phòng"]
    )

    with tab1:
        c1, c2, c3 = st.columns(3)

        with c1:
            floor_filter = st.selectbox(
                "Tầng",
                ["Tất cả", 1, 2, 3, 4, 5],
                key="room_floor_filter",
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
                ["Tất cả"] + STATUSES,
                key="room_status_filter",
            )

        result = rooms.copy()

        if not result.empty:
            if floor_filter != "Tất cả":
                result = result[result["floor"] == floor_filter]
            if type_filter != "Tất cả":
                result = result[result["room_type"] == type_filter]
            if status_filter != "Tất cả":
                result = result[result["status"] == status_filter]

        if result.empty:
            st.info("Không có phòng phù hợp.")
        else:
            display = result[
                [
                    "id",
                    "room_number",
                    "floor",
                    "room_type",
                    "price",
                    "capacity",
                    "status",
                ]
            ].rename(
                columns={
                    "id": "ID",
                    "room_number": "Phòng",
                    "floor": "Tầng",
                    "room_type": "Hạng phòng",
                    "price": "Giá",
                    "capacity": "Sức chứa",
                    "status": "Trạng thái",
                }
            )

            st.dataframe(
                display,
                column_config={
                    "Giá": st.column_config.NumberColumn(
                        "Giá",
                        format="%,.0f VNĐ",
                    )
                },
                use_container_width=True,
                hide_index=True,
            )

    with tab2:
        with st.form("add_room_form"):
            c1, c2 = st.columns(2)

            with c1:
                room_number = st.text_input("Số phòng *")
                room_type = st.selectbox(
                    "Hạng phòng",
                    list(ROOM_TYPES.keys()),
                )

            with c2:
                floor = st.number_input(
                    "Tầng",
                    min_value=1,
                    max_value=100,
                    value=1,
                )
                price = st.number_input(
                    "Giá/đêm",
                    min_value=0,
                    value=ROOM_TYPES[room_type]["price"],
                    step=100000,
                )

            capacity = st.number_input(
                "Sức chứa",
                min_value=1,
                max_value=20,
                value=ROOM_TYPES[room_type]["capacity"],
            )

            submit = st.form_submit_button(
                "➕ THÊM PHÒNG",
                use_container_width=True,
            )

            if submit:
                if not room_number.strip():
                    st.error("Vui lòng nhập số phòng.")
                else:
                    ok, msg = add_room(
                        room_number,
                        room_type,
                        floor,
                        price,
                        capacity,
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    with tab3:
        if rooms.empty:
            st.info("Chưa có phòng.")
        else:
            room_map = {
                f"{r['room_number']} - {r['room_type']}": r["id"]
                for _, r in rooms.iterrows()
            }

            selected = st.selectbox(
                "Chọn phòng",
                list(room_map.keys()),
                key="edit_room_select",
            )

            room_id = room_map[selected]
            room = rooms[rooms["id"] == room_id].iloc[0]

            with st.form("edit_room_form"):
                c1, c2 = st.columns(2)

                with c1:
                    edit_number = st.text_input(
                        "Số phòng",
                        value=str(room["room_number"]),
                    )

                    current_type = str(room["room_type"])
                    edit_type = st.selectbox(
                        "Hạng phòng",
                        list(ROOM_TYPES.keys()),
                        index=(
                            list(ROOM_TYPES.keys()).index(current_type)
                            if current_type in ROOM_TYPES
                            else 0
                        ),
                    )

                    edit_floor = st.number_input(
                        "Tầng",
                        min_value=1,
                        max_value=100,
                        value=int(room["floor"]),
                    )

                with c2:
                    edit_price = st.number_input(
                        "Giá/đêm",
                        min_value=0,
                        value=int(room["price"]),
                        step=100000,
                    )

                    edit_capacity = st.number_input(
                        "Sức chứa",
                        min_value=1,
                        max_value=20,
                        value=int(room["capacity"]),
                    )

                    edit_status = st.selectbox(
                        "Trạng thái",
                        STATUSES,
                        index=(
                            STATUSES.index(room["status"])
                            if room["status"] in STATUSES
                            else 0
                        ),
                    )

                csave, cdelete = st.columns(2)

                with csave:
                    save = st.form_submit_button(
                        "💾 LƯU",
                        use_container_width=True,
                    )

                with cdelete:
                    delete = st.form_submit_button(
                        "🗑️ XÓA",
                        use_container_width=True,
                    )

                if save:
                    ok, msg = update_room(
                        room_id,
                        edit_number,
                        edit_type,
                        edit_floor,
                        edit_price,
                        edit_capacity,
                        edit_status,
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

                if delete:
                    ok, msg = delete_room(room_id)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)


# ============================================================
# 16. HẠNG PHÒNG
# ============================================================

elif menu == "📷 Hạng phòng":
    st.title("📷 Hạng phòng & hình ảnh")
    st.caption("Mỗi hạng phòng có thể gắn một ảnh riêng. Nếu ảnh chưa được upload, app vẫn chạy bình thường.")

    room_types_list = list(ROOM_TYPES.items())
    for row_start in range(0, len(room_types_list), 2):
        cols = st.columns(2)
        for col, item in zip(cols, room_types_list[row_start:row_start + 2]):
            room_type, info = item
            with col:
                path = find_room_image(room_type)
                st.markdown('<div class="room-image-card">', unsafe_allow_html=True)
                if path:
                    st.image(str(path), use_container_width=True)
                else:
                    st.markdown('<div class="room-image-placeholder">🏨</div>', unsafe_allow_html=True)
                st.markdown('<div class="room-image-info">', unsafe_allow_html=True)
                st.markdown(f"### {safe(room_type)}")
                st.write(info["description"])
                st.caption(f"🛏️ {info['beds']} · 👥 {info['capacity']} khách · 💰 {money(info['price'])}/đêm")
                if not path:
                    st.caption(f"Ảnh cần upload: {ROOM_IMAGES[room_type][0]}")
                st.markdown('</div></div>', unsafe_allow_html=True)


# ============================================================
# 17. ĐẶT PHÒNG
# ============================================================

elif menu == "📅 Đặt phòng":
    st.title("📅 Đặt phòng")

    c1, c2 = st.columns(2)

    with c1:
        check_in = st.date_input(
            "Ngày nhận phòng",
            value=date.today(),
        )

    with c2:
        check_out = st.date_input(
            "Ngày trả phòng",
            value=date.today() + timedelta(days=1),
        )

    if check_out <= check_in:
        st.error("Ngày trả phòng phải sau ngày nhận phòng.")
    else:
        nights = (check_out - check_in).days

        room_type = st.selectbox(
            "Hạng phòng",
            list(ROOM_TYPES.keys()),
            key="booking_room_type",
        )

        info = ROOM_TYPES[room_type]

        # Kiểm tra phòng đang trống theo khoảng ngày.
        available_data = db_query("""
            SELECT r.*
            FROM rooms r
            WHERE r.room_type=%s
              AND r.status <> 'Bảo trì'
              AND NOT EXISTS (
                  SELECT 1
                  FROM bookings b
                  WHERE b.room_id=r.id
                    AND b.status NOT IN ('Hủy','Đã trả phòng')
                    AND b.check_in < %s
                    AND b.check_out > %s
              )
            ORDER BY r.room_number
        """, (
            room_type,
            check_out,
            check_in,
        ))

        available = pd.DataFrame(available_data)

        if available.empty:
            st.warning(
                "Không còn phòng phù hợp trong khoảng ngày đã chọn."
            )
        else:
            room_options = {
                f"Phòng {r['room_number']} · {money(r['price'])}/đêm": r["id"]
                for _, r in available.iterrows()
            }

            selected_room = st.selectbox(
                "Chọn phòng",
                list(room_options.keys()),
            )

            room_id = room_options[selected_room]

            room_image = find_room_image(room_type)
            if room_image:
                st.image(
                    str(room_image),
                    caption=f"{room_type} · Phòng được chọn",
                    width=520,
                )

            c1, c2 = st.columns(2)

            with c1:
                full_name = st.text_input("Họ và tên khách *")
                phone = st.text_input("Số điện thoại *")
                email = st.text_input("Email")
                id_number = st.text_input("CCCD / Passport")

            with c2:
                adults = st.number_input(
                    "Người lớn",
                    min_value=1,
                    max_value=int(info["capacity"]),
                    value=1,
                )

                max_children = max(0, int(info["capacity"]) - int(adults))

                children = st.number_input(
                    "Trẻ em",
                    min_value=0,
                    max_value=max_children,
                    value=0,
                )

                st.info(
                    f"🛏️ {room_type}\n\n"
                    f"🗓️ {nights} đêm\n\n"
                    f"💰 Tiền phòng dự kiến: "
                    f"{money(info['price'] * nights)}"
                )

            note = st.text_area("Ghi chú")

            if st.button(
                "📅 XÁC NHẬN ĐẶT PHÒNG",
                use_container_width=True,
                type="primary",
            ):
    
                if not full_name.strip():
    
                    st.error("⚠️ Vui lòng nhập tên khách.")
    
                elif not phone.strip():
    
                    st.error("⚠️ Vui lòng nhập số điện thoại.")
    
                else:
    
                    ok, msg = create_booking(
                        full_name,
                        phone,
                        email,
                        id_number,
                        room_id,
                        check_in,
                        check_out,
                        adults,
                        children,
                        note,
                    )
    
                    if ok:
    
                        # Hiển thị thông báo thành công
                        st.success(
                            "🎉 ĐẶT PHÒNG THÀNH CÔNG!"
                        )
    
                        st.info(
                            f"📋 {msg}"
                        )
    
                        # Hiển thị thêm thông tin xác nhận
                        st.markdown(
                            f"""
                            <div style="
                                padding:18px;
                                border-radius:14px;
                                background:#eef8f3;
                                border:1px solid #b8dfc9;
                                margin-top:10px;
                            ">
                                <h4 style="margin-top:0;color:#17633b;">
                                    ✓ Booking đã được ghi nhận
                                </h4>
    
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
    
                        st.balloons()
    
                        # KHÔNG st.rerun() ở đây
                        # để người dùng nhìn thấy thông báo.
    
                    else:
    
                        st.error(
                            f"❌ {msg}"
                        )


        # ============================================================
# 18. CHECK-IN / CHECK-OUT
# ============================================================

elif menu == "🛎️ Check-in / Check-out":
    st.title("🛎️ Check-in / Check-out")

    bookings = fetch_bookings()

    if bookings.empty:
        st.info("Chưa có booking.")
    else:
        c1, c2 = st.columns(2)

        with c1:
            checkin_df = bookings[
                bookings["status"] == "Đã đặt"
            ]

            if checkin_df.empty:
                st.info("Không có booking chờ check-in.")
            else:
                options = {
                    f"#{r['booking_code']} · {r['customer_name']} · Phòng {r['room_number']}": r["id"]
                    for _, r in checkin_df.iterrows()
                }

                selected = st.selectbox(
                    "Booking chờ check-in",
                    list(options.keys()),
                    key="checkin_select",
                )

                if st.button(
                    "🔵 CHECK-IN",
                    use_container_width=True,
                ):
                    ok, msg = update_booking_status(
                        options[selected],
                        "Đang ở",
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        with c2:
            checkout_df = bookings[
                bookings["status"] == "Đang ở"
            ]

            if checkout_df.empty:
                st.info("Không có khách đang ở.")
            else:
                options = {
                    f"#{r['booking_code']} · {r['customer_name']} · Phòng {r['room_number']}": r["id"]
                    for _, r in checkout_df.iterrows()
                }

                selected = st.selectbox(
                    "Khách đang ở",
                    list(options.keys()),
                    key="checkout_select",
                )

                checkout_booking_id = options[selected]
                checkout_booking = checkout_df[checkout_df["id"] == checkout_booking_id].iloc[0]
                grand_total = int(checkout_booking["grand_total"] or 0)
                paid_amount = int(checkout_booking["paid_amount"] or 0)
                remaining = max(0, grand_total - paid_amount)

                st.metric("Tổng tiền", money(grand_total))
                st.metric("Đã thanh toán", money(paid_amount))
                st.metric("Còn phải thanh toán", money(remaining))

                if remaining > 0:
                    payment_method = st.selectbox(
                        "Phương thức thanh toán",
                        PAYMENT_METHODS,
                        key="checkout_payment_method",
                    )
                    payment_note = st.text_input(
                        "Ghi chú thanh toán",
                        key="checkout_payment_note",
                        placeholder="Ví dụ: Khách thanh toán đủ khi trả phòng",
                    )
                    payment_amount = st.number_input(
                        "Số tiền thanh toán",
                        min_value=0,
                        max_value=remaining,
                        value=remaining,
                        step=50000,
                        key="checkout_payment_amount",
                    )
                else:
                    payment_method = PAYMENT_METHODS[0]
                    payment_note = "Đã thanh toán đủ trước check-out"
                    payment_amount = 0
                    st.success("Booking đã thanh toán đủ. Có thể check-out ngay.")

                if st.button(
                    "💳 THANH TOÁN & CHECK-OUT",
                    use_container_width=True,
                    type="primary",
                    key="checkout_pay_button",
                ):
                    if remaining > 0:
                        if int(payment_amount) != remaining:
                            st.error(f"Vui lòng thanh toán đủ {money(remaining)} để hoàn tất check-out.")
                        else:
                            ok_pay, msg_pay = make_payment(
                                checkout_booking_id,
                                int(payment_amount),
                                payment_method,
                                payment_note,
                            )
                            if ok_pay:
                                ok_out, msg_out = update_booking_status(
                                    checkout_booking_id,
                                    "Đã trả phòng",
                                )
                                if ok_out:
                                    st.success(f"Thanh toán thành công {money(payment_amount)} và check-out thành công.")
                                    st.rerun()
                                else:
                                    st.error(msg_out)
                            else:
                                st.error(msg_pay)
                    else:
                        ok_out, msg_out = update_booking_status(
                            checkout_booking_id,
                            "Đã trả phòng",
                        )
                        if ok_out:
                            st.success("Check-out thành công.")
                            st.rerun()
                        else:
                            st.error(msg_out)

        st.divider()
        st.dataframe(
            bookings[
                [
                    "booking_code",
                    "customer_name",
                    "room_number",
                    "check_in",
                    "check_out",
                    "status",
                    "grand_total",
                    "paid_amount",
                ]
            ],
            column_config={
                "grand_total": st.column_config.NumberColumn(
                    "Tổng tiền",
                    format="%,.0f VNĐ",
                ),
                "paid_amount": st.column_config.NumberColumn(
                    "Đã thanh toán",
                    format="%,.0f VNĐ",
                ),
            },
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# 19. KHÁCH HÀNG
# ============================================================

elif menu == "👥 Khách hàng":
    st.title("👥 Quản lý khách hàng")

    guests = fetch_guests()

    search = st.text_input(
        "🔎 Tìm khách theo tên / điện thoại / CCCD"
    )

    result = guests.copy()

    if search and not result.empty:
        mask = (
            result["full_name"].astype(str).str.contains(search, case=False, na=False)
            | result["phone"].astype(str).str.contains(search, case=False, na=False)
            | result["id_number"].astype(str).str.contains(search, case=False, na=False)
        )
        result = result[mask]

    st.dataframe(
        result,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("➕ Thêm khách hàng")

    with st.form("guest_form"):
        c1, c2 = st.columns(2)

        with c1:
            g_name = st.text_input("Họ tên *")
            g_phone = st.text_input("Điện thoại")
            g_email = st.text_input("Email")

        with c2:
            g_id = st.text_input("CCCD / Passport")
            g_address = st.text_input("Địa chỉ")

        g_note = st.text_area("Ghi chú")

        submit = st.form_submit_button(
            "LƯU KHÁCH",
            use_container_width=True,
        )

        if submit:
            if not g_name.strip():
                st.error("Vui lòng nhập họ tên.")
            else:
                try:
                    db_execute("""
                        INSERT INTO guests
                        (full_name, phone, email, id_number, address, note)
                        VALUES (%s,%s,%s,%s,%s,%s)
                    """, (
                        g_name.strip(),
                        g_phone.strip(),
                        g_email.strip(),
                        g_id.strip(),
                        g_address.strip(),
                        g_note.strip(),
                    ))
                    st.success("Đã thêm khách hàng.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


# ============================================================
# 20. DỊCH VỤ
# ============================================================

elif menu == "🧴 Dịch vụ":
    st.title("🧴 Quản lý dịch vụ")

    services = fetch_services()

    st.dataframe(
        services,
        column_config={
            "price": st.column_config.NumberColumn(
                "Giá",
                format="%,.0f VNĐ",
            )
        },
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("➕ Thêm dịch vụ")

    with st.form("service_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            code = st.text_input("Mã dịch vụ")
        with c2:
            name = st.text_input("Tên dịch vụ")
        with c3:
            price = st.number_input(
                "Giá",
                min_value=0,
                value=50000,
                step=10000,
            )

        submit = st.form_submit_button(
            "THÊM DỊCH VỤ",
            use_container_width=True,
        )

        if submit:
            ok, msg = add_service(code, name, price)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()
    st.subheader("➕ Gắn dịch vụ vào booking")

    bookings = fetch_bookings()
    active_services = services[
        services["active"] == 1
    ] if not services.empty else services

    if bookings.empty or active_services.empty:
        st.info("Cần có booking và dịch vụ.")
    else:
        booking_map = {
            f"#{r['booking_code']} · {r['customer_name']} · Phòng {r['room_number']}": r["id"]
            for _, r in bookings.iterrows()
        }

        service_map = {
            f"{r['code']} · {r['name']} · {money(r['price'])}": r["id"]
            for _, r in active_services.iterrows()
        }

        selected_booking = st.selectbox(
            "Booking",
            list(booking_map.keys()),
        )

        selected_service = st.selectbox(
            "Dịch vụ",
            list(service_map.keys()),
        )

        quantity = st.number_input(
            "Số lượng",
            min_value=1,
            max_value=100,
            value=1,
        )

        if st.button(
            "THÊM DỊCH VỤ",
            use_container_width=True,
        ):
            ok, msg = add_booking_service(
                booking_map[selected_booking],
                service_map[selected_service],
                quantity,
            )

            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


# ============================================================
# 21. HÓA ĐƠN
# ============================================================

elif menu == "🧾 Hóa đơn":
    st.title("🧾 Hóa đơn")

    bookings = fetch_bookings()

    if bookings.empty:
        st.info("Chưa có booking.")
    else:
        booking_map = {
            f"#{r['booking_code']} · {r['customer_name']} · Phòng {r['room_number']}": r["id"]
            for _, r in bookings.iterrows()
        }

        selected = st.selectbox(
            "Chọn booking",
            list(booking_map.keys()),
        )

        booking_id = booking_map[selected]
        booking = bookings[bookings["id"] == booking_id].iloc[0]

        payments = fetch_payments(booking_id)

        service_rows = db_query("""
            SELECT
                bs.*,
                s.code,
                s.name
            FROM booking_services bs
            JOIN services s ON s.id=bs.service_id
            WHERE bs.booking_id=%s
            ORDER BY bs.id
        """, (booking_id,))

        st.markdown(
            f"""
            <div class="hero">
                <div class="hero-title">CHARM PEARL HOTEL</div>
                <div class="hero-sub">HÓA ĐƠN / INVOICE</div>
                <hr>
                <b>Mã booking:</b> {safe(booking["booking_code"])}<br>
                <b>Khách:</b> {safe(booking["customer_name"])}<br>
                <b>Điện thoại:</b> {safe(booking["phone"])}<br>
                <b>Phòng:</b> {safe(booking["room_number"])}<br>
                <b>Check-in:</b> {booking["check_in"]}<br>
                <b>Check-out:</b> {booking["check_out"]}<br>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Tiền phòng", money(booking["room_total"]))
        c2.metric("Dịch vụ", money(booking["service_total"]))
        c3.metric("Tổng", money(booking["grand_total"]))

        remaining = int(booking["grand_total"]) - int(booking["paid_amount"])
        c4.metric("Còn lại", money(max(0, remaining)))

        if service_rows:
            st.subheader("🧴 Dịch vụ")
            service_df = pd.DataFrame(service_rows)
            st.dataframe(
                service_df[
                    ["code", "name", "quantity", "unit_price", "total_price"]
                ],
                column_config={
                    "unit_price": st.column_config.NumberColumn(
                        "Đơn giá",
                        format="%,.0f VNĐ",
                    ),
                    "total_price": st.column_config.NumberColumn(
                        "Thành tiền",
                        format="%,.0f VNĐ",
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )

        st.subheader("💳 Lịch sử thanh toán")

        if payments.empty:
            st.info("Chưa có thanh toán.")
        else:
            st.dataframe(
                payments[
                    [
                        "amount",
                        "payment_method",
                        "note",
                        "created_at",
                    ]
                ],
                column_config={
                    "amount": st.column_config.NumberColumn(
                        "Số tiền",
                        format="%,.0f VNĐ",
                    )
                },
                use_container_width=True,
                hide_index=True,
            )

        invoice_text = f"""
CHARM PEARL HOTEL
VŨNG TÀU
--------------------------------
Mã booking: {booking["booking_code"]}
Khách hàng: {booking["customer_name"]}
Điện thoại: {booking["phone"]}
Phòng: {booking["room_number"]}
Check-in: {booking["check_in"]}
Check-out: {booking["check_out"]}
Số đêm: {booking["nights"]}
--------------------------------
Tiền phòng: {money(booking["room_total"])}
Dịch vụ: {money(booking["service_total"])}
TỔNG CỘNG: {money(booking["grand_total"])}
ĐÃ THANH TOÁN: {money(booking["paid_amount"])}
CÒN LẠI: {money(max(0, remaining))}
--------------------------------
Cảm ơn quý khách!
"""

        st.download_button(
            "⬇️ TẢI HÓA ĐƠN TXT",
            invoice_text,
            file_name=f"{booking['booking_code']}.txt",
            mime="text/plain",
            use_container_width=True,
        )


# ============================================================
# 22. DOANH THU
# ============================================================

elif menu == "💰 Doanh thu":
    st.title("💰 Doanh thu")

    payments = fetch_payments()

    if payments.empty:
        st.info("Chưa có dữ liệu thanh toán.")
    else:
        payments["created_at"] = pd.to_datetime(payments["created_at"])

        total_paid = int(payments["amount"].sum())

        c1, c2, c3 = st.columns(3)

        c1.metric("Tổng tiền đã thu", money(total_paid))
        c2.metric("Số giao dịch", len(payments))
        c3.metric(
            "Giao dịch lớn nhất",
            money(payments["amount"].max()),
        )

        st.divider()

        monthly = (
            payments
            .assign(month=payments["created_at"].dt.to_period("M").astype(str))
            .groupby("month")["amount"]
            .sum()
            .reset_index()
        )

        st.subheader("📈 Doanh thu theo tháng")
        st.bar_chart(
            monthly.set_index("month")["amount"]
        )

        st.subheader("💳 Theo phương thức thanh toán")

        method = (
            payments
            .groupby("payment_method")["amount"]
            .sum()
            .sort_values(ascending=False)
        )

        st.bar_chart(method)

        st.subheader("📋 Chi tiết")
        st.dataframe(
            payments,
            column_config={
                "amount": st.column_config.NumberColumn(
                    "Số tiền",
                    format="%,.0f VNĐ",
                )
            },
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# 23. CHATBOX
# ============================================================
 
elif menu == "💬 Chat với khách": 
 
    st.title("💬 Charm Pearl AI") 
    st.caption("Trợ lý ảo của Charm Pearl Hotel · Vũng Tàu") 
 
    # ----------------------------------------------------- 
    # Khởi tạo lịch sử chat 
    # ----------------------------------------------------- 
 
    if "chat_history" not in st.session_state: 
        st.session_state.chat_history = [ 
            { 
                "role": "assistant", 
                "content": 
                    "Xin chào! Tôi là trợ lý ảo của Charm Pearl Hotel. " 
                    "Tôi có thể giúp anh/chị kiểm tra phòng trống, " 
                    "giá phòng, hạng phòng và thông tin khách sạn." 
            } 
        ] 
 
    # ----------------------------------------------------- 
    # HIỂN THỊ LỊCH SỬ CHAT 
    # ----------------------------------------------------- 
 
    for message in st.session_state.chat_history: 
 
        with st.chat_message(message["role"]): 
 
            st.markdown(message["content"]) 
 
    # ----------------------------------------------------- 
    # HÀM TRẢ LỜI CHATBOT 
    # ----------------------------------------------------- 
 
    def chatbot_reply(question): 
 
        q = question.lower().strip() 
 
        rooms = fetch_rooms()
 
        # ================================================= 
        # 1. KIỂM TRA KHÁCH HỎI PHÒNG TRỐNG 
        # ================================================= 
 
        asking_available = any( 
            keyword in q 
            for keyword in [ 
                "còn phòng", 
                "phòng trống", 
                "còn phòng trống", 
                "phòng nào còn", 
                "phòng còn", 
                "còn phòng nào", 
                "phòng có sẵn", 
                "available room", 
                "available" 
            ] 
        ) 
 
        # ================================================= 
        # 2. XÁC ĐỊNH HẠNG PHÒNG KHÁCH ĐANG HỎI 
        # ================================================= 
 
        room_type = None 
 
        room_keywords = { 
            "deluxe room king": "Deluxe Room King", 
            "deluxe king": "Deluxe Room King", 
            "deluxe room twins": "Deluxe Room Twins", 
            "deluxe twins": "Deluxe Room Twins", 
            "twin": "Deluxe Room Twins", 
            "premier garden": "Premier Garden", 
            "premier ocean": "Premier Ocean", 
            "premier": "Premier Ocean", 
            "princess suite": "Princess Suite", 
            "princess": "Princess Suite", 
            "royal suite villa": "Royal Suite Villa", 
            "royal suite": "Royal Suite Villa", 
            "villa": "Royal Suite Villa" 
        } 
 
        for keyword, name in room_keywords.items(): 
 
            if keyword in q: 
                room_type = name 
                break 
 
        # ================================================= 
        # 3. KHÁCH HỎI PHÒNG TRỐNG 
        # ================================================= 
 
        if asking_available: 
 
            available = rooms[ 
                rooms["status"].astype(str).str.lower() == "trống" 
            ].copy() 
 
            # --------------------------------------------- 
            # Nếu hỏi một hạng phòng cụ thể 
            # --------------------------------------------- 
 
            if room_type: 
 
                available = available[ 
                    available["room_type"] == room_type 
                ] 
 
                if available.empty: 
 
                    return ( 
                        f"Hiện tại Charm Pearl Hotel " 
                        f"không còn phòng trống thuộc hạng " 
                        f"**{room_type}**." 
                    ) 
 
                room_list = ", ".join( 
                    available["room_number"] 
                    .astype(str) 
                    .tolist() 
                ) 
 
                price = available.iloc[0]["price"] 
 
                return ( 
                    f"Hiện tại **{room_type}** vẫn còn " 
                    f"**{len(available)} phòng trống**.\n\n" 
                    f"Phòng: **{room_list}**\n\n" 
                    f"Giá phòng: **{money(price)} / đêm**." 
                ) 
 
            # --------------------------------------------- 
            # Nếu hỏi tất cả phòng 
            # --------------------------------------------- 
 
            if available.empty: 
 
                return ( 
                    "Hiện tại khách sạn không còn phòng " 
                    "đang ở trạng thái **Trống**." 
                ) 
 
            result = [] 
 
            for rt in ROOM_TYPES.keys(): 
 
                data = available[ 
                    available["room_type"] == rt 
                ] 
 
                if not data.empty: 
 
                    room_list = ", ".join( 
                        data["room_number"] 
                        .astype(str) 
                        .tolist() 
                    ) 
 
                    price = data.iloc[0]["price"] 
 
                    result.append( 
                        f"**{rt}** — {len(data)} phòng " 
                        f"({room_list}) · " 
                        f"{money(price)}/đêm" 
                    ) 
 
            return ( 
                f"Hiện tại Charm Pearl Hotel còn " 
                f"**{len(available)} phòng trống**:\n\n" 
                + "\n\n".join(result) 
            ) 
 
        # ================================================= 
        # 4. KHÁCH HỎI GIÁ PHÒNG 
        # ================================================= 
 
        asking_price = any( 
            keyword in q 
            for keyword in [ 
                "giá phòng", 
                "bao nhiêu tiền", 
                "bao nhiêu", 
                "giá bao nhiêu", 
                "giá", 
                "price" 
            ] 
        ) 
 
        if asking_price: 
 
            if room_type: 
 
                info = ROOM_TYPES.get(room_type) 
 
                if info: 
 
                    return ( 
                        f"**{room_type}**\n\n" 
                        f"Giá: **{money(info['price'])}/đêm**\n\n" 
                        f"Sức chứa tối đa: **{info['capacity']} khách**." 
                    ) 
 
            # Nếu hỏi giá nhưng không nói rõ hạng 
            result = [] 
 
            for rt, info in ROOM_TYPES.items(): 
 
                result.append( 
                    f"**{rt}**: " 
                    f"{money(info['price'])}/đêm · " 
                    f"Tối đa {info['capacity']} khách" 
                ) 
 
            return ( 
                "Hiện Charm Pearl Hotel có các hạng phòng:\n\n" 
                + "\n\n".join(result) 
            ) 
 
        # ================================================= 
        # 5. KHÁCH HỎI HẠNG PHÒNG 
        # ================================================= 
 
        if any( 
            keyword in q 
            for keyword in [ 
                "hạng phòng", 
                "loại phòng", 
                "có những phòng", 
                "các phòng", 
                "phòng nào", 
                "phòng gì" 
            ] 
        ): 
 
            result = [] 
 
            for rt, info in ROOM_TYPES.items(): 
 
                result.append( 
                    f"**{rt}** — " 
                    f"{money(info['price'])}/đêm · " 
                    f"Tối đa {info['capacity']} khách" 
                ) 
 
            return ( 
                "Charm Pearl Hotel hiện có 6 hạng phòng:\n\n" 
                + "\n\n".join(result) 
            ) 
 
        # ================================================= 
        # 6. CHECK-IN / CHECK-OUT 
        # ================================================= 
 
        if "check-in" in q or "check in" in q: 
 
            return ( 
                "Giờ check-in tiêu chuẩn của khách sạn là " 
                "**14:00**." 
            ) 
 
        if "check-out" in q or "check out" in q: 
 
            return ( 
                "Giờ check-out tiêu chuẩn của khách sạn là " 
                "**12:00**." 
            ) 
 
        # ================================================= 
        # 7. ĐỊA CHỈ 
        # ================================================= 
 
        if any( 
            keyword in q 
            for keyword in [ 
                "địa chỉ", 
                "ở đâu", 
                "địa điểm", 
                "vị trí" 
            ] 
        ): 
 
            return ( 
                "Charm Pearl Hotel tọa lạc tại " 
                "**Vũng Tàu**." 
            ) 
 
        # ================================================= 
        # 8. DỊCH VỤ 
        # ================================================= 
 
        if any( 
            keyword in q 
            for keyword in [ 
                "dịch vụ", 
                "có gì", 
                "tiện nghi", 
                "tiện ích" 
            ] 
        ): 
 
            return ( 
                "Charm Pearl Hotel cung cấp nhiều dịch vụ " 
                "như ăn sáng, cà phê, giặt ủi, minibar, " 
                "Extra Bed, spa và đưa đón sân bay." 
            ) 
 
        # ================================================= 
        # 9. ĐẶT PHÒNG 
        # ================================================= 
 
        if any( 
            keyword in q 
            for keyword in [ 
                "đặt phòng", 
                "book phòng", 
                "booking", 
                "muốn đặt" 
            ] 
        ): 
 
            return ( 
                "Anh/chị có thể đặt phòng trực tiếp tại mục " 
                "**Đặt phòng** trên hệ thống. " 
                "Tại đó có thể chọn ngày, hạng phòng và " 
                "phòng cụ thể." 
            ) 
 
        # ================================================= 
        # 10. CHÀO HỎI 
        # ================================================= 
 
        if any( 
            keyword in q 
            for keyword in [ 
                "xin chào", 
                "hello", 
                "hi", 
                "chào" 
            ] 
        ): 
 
            return ( 
                "Xin chào! Tôi là **Charm Pearl AI**. " 
                "Anh/chị muốn kiểm tra phòng trống, " 
                "giá phòng hay thông tin khách sạn?" 
            ) 
 
        # ================================================= 
        # 11. KHÔNG HIỂU 
        # ================================================= 
 
        return ( 
            "Tôi có thể hỗ trợ anh/chị về:\n\n" 
            "- Phòng còn trống\n" 
            "- Giá phòng\n" 
            "- Các hạng phòng\n" 
            "- Sức chứa\n" 
            "- Giờ check-in / check-out\n" 
            "- Dịch vụ khách sạn\n" 
            "- Đặt phòng\n\n" 
            "Anh/chị có thể hỏi ví dụ: " 
            "**“Còn phòng Premier Ocean không?”**" 
        ) 
 
    # ===================================================== 
    # Ô NHẬP CHAT 
    # ===================================================== 
 
    question = st.chat_input( 
        "Nhập câu hỏi cho Charm Pearl AI..." 
    ) 
 
    if question: 
 
        # Hiện câu hỏi khách 
        st.session_state.chat_history.append({ 
            "role": "user", 
            "content": question 
        }) 
 
        # Tạo câu trả lời 
        answer = chatbot_reply(question) 
 
        # Lưu câu trả lời 
        st.session_state.chat_history.append({ 
            "role": "assistant", 
            "content": answer 
        }) 
 
        # Reload để hiển thị tin nhắn mới 
        st.rerun() 

# ============================================================
# 24. BÁO CÁO
# ============================================================

elif menu == "📊 Báo cáo":
    st.title("📊 Báo cáo quản lý")

    rooms = fetch_rooms()
    bookings = fetch_bookings()

    if bookings.empty:
        st.info("Chưa có dữ liệu booking.")
    else:
        bookings["check_in"] = pd.to_datetime(bookings["check_in"])
        bookings["check_out"] = pd.to_datetime(bookings["check_out"])

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Tổng booking", len(bookings))
        c2.metric(
            "Booking hoàn tất",
            len(bookings[bookings["status"] == "Đã trả phòng"]),
        )
        c3.metric(
            "Booking hủy",
            len(bookings[bookings["status"] == "Hủy"]),
        )
        c4.metric(
            "Doanh thu phát sinh",
            money(bookings["grand_total"].sum()),
        )

        st.divider()

        st.subheader("📅 Booking theo trạng thái")

        status_report = (
            bookings["status"]
            .value_counts()
            .rename_axis("status")
            .reset_index(name="count")
        )

        st.bar_chart(
            status_report.set_index("status")["count"]
        )

        st.subheader("🏨 Doanh thu theo hạng phòng")

        room_report = (
            bookings
            .groupby("room_type")["grand_total"]
            .sum()
            .sort_values(ascending=False)
        )

        st.bar_chart(room_report)

        st.subheader("📋 Bảng báo cáo")

        report = bookings[
            [
                "booking_code",
                "customer_name",
                "room_number",
                "room_type",
                "check_in",
                "check_out",
                "nights",
                "status",
                "room_total",
                "service_total",
                "grand_total",
                "paid_amount",
            ]
        ].copy()

        report["Còn lại"] = (
            report["grand_total"] - report["paid_amount"]
        )

        st.dataframe(
            report,
            column_config={
                "room_total": st.column_config.NumberColumn(
                    "Tiền phòng",
                    format="%,.0f VNĐ",
                ),
                "service_total": st.column_config.NumberColumn(
                    "Dịch vụ",
                    format="%,.0f VNĐ",
                ),
                "grand_total": st.column_config.NumberColumn(
                    "Tổng",
                    format="%,.0f VNĐ",
                ),
                "paid_amount": st.column_config.NumberColumn(
                    "Đã thu",
                    format="%,.0f VNĐ",
                ),
                "Còn lại": st.column_config.NumberColumn(
                    "Còn lại",
                    format="%,.0f VNĐ",
                ),
            },
            use_container_width=True,
            hide_index=True,
        )

# ============================================================
# FOOTER
# ============================================================

st.sidebar.divider()
st.sidebar.caption(
    f"🏨 {HOTEL_NAME} · {LOCATION}"
)
st.sidebar.caption(
    f"Cập nhật: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
)
