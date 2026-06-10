# RUN_COMPOSE.md – Hướng dẫn chạy Lab 05

Tài liệu này hướng dẫn người khác clone repo sạch và chạy lại stack Compose của Lab 05.

---

## 1. Clone repo

```bash
git clone <repo-url>
cd FIT4110_lab05_docker_compose_readiness
```

---

## 2. Cài dependencies cho Newman/Prism/Spectral (tuỳ chọn)

```bash
npm ci
```

---

## 3. Build & chạy stack Docker Compose

```bash
# Copy .env.example sang .env nếu muốn thay đổi giá trị mặc định
cp .env.example .env

# Build images, khởi động container và chờ tất cả healthcheck pass
docker compose up -d --build --wait
```

Lệnh trên sẽ tạo các container:

- `fit4110-db-lab05` (PostgreSQL)
- `fit4110-ai-lab05` (AI service mẫu chạy non-root trên port 9000)
- `fit4110-api-lab05` (API FastAPI trên port 8000)

API dùng hostname nội bộ `db` và `ai-service`; endpoint `/health` chỉ trả `200`
khi cả PostgreSQL và AI service đều sẵn sàng.

Theo dõi log:

```bash
docker compose logs -f
```

Sau vài giây, kiểm tra health của mỗi service:

```bash
# API
curl http://localhost:8000/health

# AI service
curl http://localhost:9000/health

# DB readiness
docker exec -it fit4110-db-lab05 pg_isready -U $POSTGRES_USER
```

Bạn cũng có thể truy cập endpoint `/predict` của AI service để xem kết quả mẫu:

```bash
curl -X POST http://localhost:9000/predict
```

---

## 4. Chạy Newman test trên stack Compose

```bash
npm run test:compose
```

Report sinh tại:

```text
reports/newman-lab05-compose.xml
reports/newman-lab05-compose.html
```

Khi commit được push lên nhánh `main`, GitHub Actions tự publish:

```text
ghcr.io/connectivity-services-ad-pt/iot-ingestion:v0.1.0-team-iot
ghcr.io/connectivity-services-ad-pt/ai-service:v0.1.0-team-iot
```

Workflow dùng `GITHUB_TOKEN`, vì vậy không cần đăng nhập Docker Desktop.

---

## 5. Dừng stack

Khi không cần nữa, dừng và xoá các container bằng:

```bash
docker compose down
```

Nếu muốn xoá volume dữ liệu của DB, thêm tuỳ chọn `-v`:

```bash
docker compose down -v
```

---

## 6. Lệnh nhanh

Bạn có thể dùng Makefile:

```bash
make compose-up
make compose-down
make logs
```

---

## 7. Mẹo gỡ lỗi

- Sử dụng `docker compose ps` để xem trạng thái container.
- Nếu API trả lỗi kết nối DB, hãy kiểm tra biến môi trường `POSTGRES_*` trong `.env` và đảm bảo DB đã sẵn sàng (`pg_isready`).
- Nếu AI service cần tải mô hình lớn, tăng `start_period` của healthcheck trong `docker-compose.yml`.
