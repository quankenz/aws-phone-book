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