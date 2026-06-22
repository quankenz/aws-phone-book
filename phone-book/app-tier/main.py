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