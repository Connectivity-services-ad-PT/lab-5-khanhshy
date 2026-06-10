# Readiness Checklist – Lab 05

Đây là danh sách kiểm tra (checklist) để đảm bảo stack Docker Compose của bạn đã sẵn sàng trước khi gửi bài. Hãy tick vào mỗi mục sau khi hoàn thành.

- [x] **Database ready:** container DB đã chạy và phản hồi `pg_isready`.
- [x] **AI service ready:** container AI chạy non-root, `/health` trả `200` và `/predict` hoạt động.
- [x] **API ready:** `/health` trả `200`; Newman tạo và đọc lại reading từ PostgreSQL thành công.
- [x] **Environment variables:** `.env.example` chứa cấu hình mẫu; `.env` cục bộ được ignore và không có secret thật trong Git.
- [x] **Network & Ports:** API gọi được AI bằng hostname `ai-service`; API/AI map ports 8000/9000, DB chỉ mở trong network nội bộ.
- [x] **Image tags:** hai image `v0.1.0-team-iot` đã được workflow push thành công lên GHCR.

Ghi chú thêm những vấn đề gặp phải hoặc điều chỉnh tại đây:

```text
- 2026-06-10: Compose healthy; Newman pass 5 requests và 9 assertions.
- GHCR targets: `ghcr.io/connectivity-services-ad-pt/iot-ingestion:v0.1.0-team-iot` và `ghcr.io/connectivity-services-ad-pt/ai-service:v0.1.0-team-iot`.
- GitHub Actions run `27251877157`: đăng nhập GHCR và push cả hai image thành công.
```
