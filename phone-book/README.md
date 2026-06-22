Để chuyển đổi cấu trúc gốc của bạn thành mô hình **3-Tier Production** không dùng Docker, chúng ta sẽ viết lại hoàn chỉnh mã nguồn.

Ứng dụng sẽ được chia làm 2 phần độc lập: **Web Tier** (chạy Single Page App bằng JavaScript, upload trực tiếp lên S3) và **App Tier** (REST API Engine bằng Python Flask, chạy trên EC2 kết hợp WSGI Server Gunicorn).

---

## 🏢 TẦNG 1: WEB TIER (Frontend — Triển khai lên S3 + CloudFront)

Toàn bộ logic chuyển trang (`index.html`, `add-update.html`, `delete.html`) trước đây dùng cơ chế Render của Python/Jinja2 nay được **gộp và chuyển hóa thành Single Page App (SPA) thuần Client-side** sử dụng Vanilla JS `fetch()`.

Bạn lưu file này thành `index.html` và upload trực tiếp lên S3 Bucket.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AWS Production - PhoneBook</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {
      min-height: 100vh;
      background: linear-gradient(135deg, #7af, #f7f);
      padding-top: 30px;
    }
    .main-card {
      border-radius: 15px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    }
  </style>
</head>
<body>
  <div class="container col-md-8 col-lg-6">
    <div class="card main-card bg-white p-4 mb-4">
      <h1 class="text-center h3 text-primary mb-3">Project: Phonebook Application</h1>
      <h5 class="text-center text-muted mb-4">AWS 3-Tier Production Architecture</h5>

      <div class="mb-4 p-3 bg-light rounded">
        <label class="form-label fw-bold">Search Contact:</label>
        <div class="input-group">
          <input type="text" id="search-keyword" class="form-control" placeholder="Enter name to search...">
          <button class="btn btn-primary" onclick="searchContacts()">Search</button>
          <button class="btn btn-secondary" onclick="loadAllContacts()">Clear</button>
        </div>
      </div>

      <div class="mb-4 p-3 border rounded">
        <h5 class="text-secondary id="form-action-title">Add New Person</h5>
        <form id="contact-form">
          <input type="hidden" id="contact-id">
          <div class="mb-3">
            <label class="form-label">Name:</label>
            <input type="text" id="contact-name" class="form-control" required placeholder="e.g. John Doe">
          </div>
          <div class="mb-3">
            <label class="form-label">Phone Number:</label>
            <input type="text" id="contact-phone" class="form-control" required placeholder="e.g. 0912345678">
          </div>
          <button type="submit" id="submit-btn" class="btn btn-success w-100">Add to Phonebook</button>
          <button type="button" id="cancel-btn" class="btn btn-link w-100 d-none" onclick="resetForm()">Cancel Edit</button>
        </form>
      </div>

      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead class="table-dark">
            <tr>
              <th>Name</th>
              <th>Phone Number</th>
              <th class="text-center">Actions</th>
            </tr>
          </thead>
          <tbody id="phonebook-entries">
            <tr><td colspan="3" class="text-center text-muted">Loading contacts...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    // BEST PRACTICE: Sử dụng Relative Path để CloudFront định tuyến chuẩn Behavior sang ALB
    // Khi test local, bạn có thể đổi thành: const API_BASE = 'http://<ALB-DNS-OR-LOCAL-IP>:8080';
    const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8080' : '';

    document.addEventListener('DOMContentLoaded', loadAllContacts);

    function loadAllContacts() {
      document.getElementById('search-keyword').value = '';
      fetch(`${API_BASE}/api/contacts`)
        .then(res => res.json())
        .then(renderTable)
        .catch(err => alert('Error connecting to backend API: ' + err));
    }

    function searchContacts() {
      const keyword = document.getElementById('search-keyword').value.trim();
      if (!keyword) return loadAllContacts();
      fetch(`${API_BASE}/api/contacts/search?keyword=${encodeURIComponent(keyword)}`)
        .then(res => res.json())
        .then(renderTable);
    }

    function renderTable(data) {
      const tbody = document.getElementById('phonebook-entries');
      tbody.innerHTML = '';
      if(data.length === 0 || (data.length === 1 && data[0].name === "No Result")) {
        tbody.innerHTML = `<tr><td colspan="3" class="text-center text-danger fw-bold">No Result Found</td></tr>`;
        return;
      }
      data.forEach(item => {
        tbody.innerHTML += `
          <tr>
            <td class="fw-bold">${item.name}</td>
            <td>${item.number}</td>
            <td class="text-center">
              <button class="btn btn-sm btn-warning me-2" onclick="initEdit(${item.id}, '${item.name}', '${item.number}')">Edit</button>
              <button class="btn btn-sm btn-danger" onclick="deleteContact(${item.id})">Delete</button>
            </td>
          </tr>
        `;
      });
    }

    document.getElementById('contact-form').addEventListener('submit', function(e) {
      e.preventDefault();
      const id = document.getElementById('contact-id').value;
      const name = document.getElementById('contact-name').value;
      const number = document.getElementById('contact-phone').value;

      const payload = { name, number };
      const url = id ? `${API_BASE}/api/contacts/${id}` : `${API_BASE}/api/contacts`;
      const method = id ? 'PUT' : 'POST';

      fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(data => {
        resetForm();
        loadAllContacts();
      });
    });

    function initEdit(id, name, number) {
      document.getElementById('contact-id').value = id;
      document.getElementById('contact-name').value = name;
      document.getElementById('contact-phone').value = number;
      document.getElementById('form-action-title').innerText = "Update Person Data";
      document.getElementById('submit-btn').innerText = "Update Record";
      document.getElementById('submit-btn').className = "btn btn-warning w-100";
      document.getElementById('cancel-btn').classList.remove('d-none');
    }

    function resetForm() {
      document.getElementById('contact-id').value = '';
      document.getElementById('contact-form').reset();
      document.getElementById('form-action-title').innerText = "Add New Person";
      document.getElementById('submit-btn').innerText = "Add to Phonebook";
      document.getElementById('submit-btn').className = "btn btn-success w-100";
      document.getElementById('cancel-btn').classList.add('d-none');
    }

    function deleteContact(id) {
      if(confirm("Are you sure you want to delete this record?")) {
        fetch(`${API_BASE}/api/contacts/${id}`, { method: 'DELETE' })
          .then(() => loadAllContacts());
      }
    }
  </script>
</body>
</html>

```

---

## ⚙️ TẦNG 2: APP TIER (Backend REST API — Triển khai lên EC2)

Mã nguồn Python Flask được viết lại hoàn chỉnh theo chuẩn **REST API sạch**. Nó loại bỏ các hàm trả về giao diện HTML (`render_template`), cấu hình hệ thống log tập trung sang `sys.stdout` (chuẩn hóa đẩy log về CloudWatch), bổ sung cơ chế kiểm tra trạng thái **Health Check** (yêu cầu bắt buộc của AWS ALB), và tích hợp pool kết nối tự động.

Bạn lưu file này thành `main.tf` hoặc `main.py` tùy ý thuộc backend.

```python
# main.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from mysql.connector import pooling
import os
import logging
import sys

app = Flask(__name__)
# BEST PRACTICE: Bật CORS cho phép Web Tier từ CloudFront có thể tạo request chéo an toàn
CORS(app)

# Cấu hình logging đẩy về thiết bị tiêu chuẩn để CloudWatch Agent thu thập
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')

# BEST PRACTICE: Lấy cấu hình bảo mật 100% từ Environment Variables trên EC2 OS System
DB_HOST = os.getenv("MYSQL_HOST")
DB_USER = os.getenv("MYSQL_USER")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD")
DB_NAME = os.getenv("DATABASE_NAME", "phonebook")

# Khởi tạo Connection Pool tối ưu hiệu năng kết nối tới RDS tránh overload kết nối vật lý
try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="phonebook_pool",
        pool_size=10, # Giới hạn tối đa 10 kết nối đồng thời cho mỗi EC2
        pool_reset_session=True,
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    app.logger.info("Database Connection Pool successfully initialized.")
except Exception as e:
    app.logger.error(f"Critical error initializing Database Connection Pool: {str(e)}")
    db_pool = None

def init_db_structure():
    """Tự động kiểm tra và khởi tạo database schema trên RDS nếu chưa có"""
    if not db_pool: return
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor()
        # Tạo database nếu chưa tồn tại
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.execute(f"USE {DB_NAME};")
        # Tạo bảng phonebook
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phonebook(
                id INT NOT NULL AUTO_INCREMENT,
                name VARCHAR(100) NOT NULL,
                number VARCHAR(100) NOT NULL,
                PRIMARY KEY (id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        conn.commit()
        cursor.close()
        conn.close()
        app.logger.info("Database validation & initialization complete.")
    except Exception as e:
        app.logger.error(f"Failed to initialize database structures: {str(e)}")

# TARGET GROUP HEALTH CHECK ENDPOINT
# Cực kỳ quan trọng: Application Load Balancer sẽ ping liên tục vào đây để định danh EC2 sống/chết
@app.route("/health", methods=["GET"])
def health():
    if not db_pool:
        return jsonify({"status": "UNHEALTHY", "reason": "No Database configuration set"}), 500
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"status": "HEALTHY", "engine": "Flask REST API", "rds": "CONNECTED"}), 200
    except Exception as e:
        return jsonify({"status": "UNHEALTHY", "reason": str(e)}), 500

# API: LẤY TOÀN BỘ CONTACT
@app.route("/api/contacts", methods=["GET"])
def get_all():
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, number FROM phonebook ORDER BY id DESC;")
        records = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(records), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API: TÌM KIẾM THEO TÊN
@app.route("/api/contacts/search", methods=["GET"])
def search():
    keyword = request.args.get('keyword', '').strip()
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, name, number FROM phonebook WHERE LOWER(name) LIKE %s;"
        cursor.execute(query, (f"%{keyword.lower()}%",))
        records = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(records), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API: THÊM MỚI RECORD
@app.route("/api/contacts", methods=["POST"])
def create():
    data = request.get_json()
    if not data or 'name' not in data or 'number' not in data:
        return jsonify({"message": "Invalid payload format"}), 400
    
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor()
        query = "INSERT INTO phonebook (name, number) VALUES (%s, %s);"
        cursor.execute(query, (data['name'].strip(), data['number'].strip()))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Contact created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API: CẬP NHẬT RECORD
@app.route("/api/contacts/<int:id>", methods=["PUT"])
def update(id):
    data = request.get_json()
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor()
        query = "UPDATE phonebook SET name = %s, number = %s WHERE id = %s;"
        cursor.execute(query, (data['name'].strip(), data['number'].strip(), id))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Contact updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API: XÓA RECORD
@app.route("/api/contacts/<int:id>", methods=["DELETE"])
def delete(id):
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor()
        query = "DELETE FROM phonebook WHERE id = %s;"
        cursor.execute(query, (id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Contact deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    init_db_structure()
    # Chạy dự phòng ở môi trường local debug, thực tế trên EC2 sẽ chạy qua WSGI Gunicorn
    app.run(host="0.0.0.0", port=8080)

```

#### File `requirements.txt` tối ưu cho EC2 Linux:

```text
flask==2.1.3
Werkzeug==2.2.2
flask-cors==3.0.10
mysql-connector-python==8.0.33
gunicorn==20.1.0

```

---

## 🚀 KỊCH BẢN TRIỂN KHAI VÀ KHỞI CHẠY KHÔNG CẦN DOCKER TRÊN AWS

Để bạn tự động hóa hoàn toàn việc cấu hình máy chủ ứng dụng mà không cần click tay cài đặt từng thành phần, hãy tận dụng tính năng **User Data (Shell Script)** của AWS khi khởi tạo EC2 Instance (hoặc cấu hình trong Launch Template của Auto Scaling Group).

### AWS EC2 User Data (Automation Shell Script)

Đoạn mã tự động hóa này viết riêng cho hệ điều hành **Amazon Linux 2023** (Hệ điều hành chuẩn hiện tại của AWS):

```bash
#!/bin/bash
# 1. Cập nhật hệ thống và cài đặt Python 3, thư viện môi trường nền
dnf update -y
dnf install python3-pip python3-devel gcc git -y

# 2. Tạo cấu trúc thư mục ứng dụng production và chuẩn bị code
mkdir -p /opt/phonebook-app
cd /opt/phonebook-app

# [Hành động thực tế]: Tải code của bạn từ S3 hoặc Git về đây
# Ví dụ: aws s3 cp s3://my-app-deployment-bucket/backend/ . --recursive
# Ở đây ta giả lập file main.py và requirements.txt đã có tại thư mục này

# 3. Cài đặt các thư viện Python độc lập trực tiếp lên hệ thống
pip3 install --no-cache-dir -r requirements.txt

# 4. BEST PRACTICE: Tạo file cấu hình dịch vụ Systemd để quản lý ứng dụng chạy ngầm tự động
cat <<EOF > /etc/systemd/system/phonebook.service
[Unit]
Description=Gunicorn instance to serve Phonebook REST API
After=network.target

[Service]
User=root
WorkingDirectory=/opt/phonebook-app

# Định nghĩa các biến môi trường cấu hình hạ tầng mạng AWS của bạn tại đây
Environment="MYSQL_HOST=database-1.cluster-xxxxxxxx.ap-southeast-1.rds.amazonaws.com"
Environment="MYSQL_USER=admin"
Environment="MYSQL_PASSWORD=MậtKhẩuRDSBảoMậtCủaBạn"
Environment="DATABASE_NAME=phonebook"

# Khởi chạy Gunicorn đa tiến trình (Số Worker = 2 * Số Core CPU + 1)
ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 0.0.0.0:8080 main:app --access-logfile - --error-logfile -

Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 5. Kích hoạt và cho phép ứng dụng khởi động cùng hệ thống máy chủ AWS
systemctl daemon-reload
systemctl start phonebook
systemctl enable phonebook

```

### Kiến thức Network & Gateway bổ trợ:

Khi bạn đưa cấu trúc này lên AWS, hãy thiết lập **CloudFront Behaviors**:

1. Path Pattern `Default (*)` ➡️ Trỏ tới S3 Origin (Phục vụ file giao diện `index.html`).
2. Path Pattern `/api/*` và `/health` ➡️ Trỏ tới Application Load Balancer Origin (Định tuyến yêu cầu xử lý logic xuống các máy chủ EC2 ở mạng riêng).

Mô hình này giúp ứng dụng hoạt động theo cơ chế Single Domain, loại bỏ hoàn toàn lỗi phiền toái liên quan đến CORS khi triển khai hệ thống phân tán đa tầng!