# Báo Cáo Khai Báo Sử Dụng AI (AI Usage Disclosure)

Tuân thủ quy định học vụ tại [RULES.md](../docs/RULES.md) của khóa học K4-Track02-Day18, học viên khai báo minh bạch phạm vi và mục đích sử dụng các công cụ trợ lý AI trong bài lab này như sau:

## 1. Công cụ AI sử dụng
- **Trợ lý:** Antigravity IDE (Gemini 3.8 Flash).
- **Rà soát và chỉnh sửa bổ sung ngày 04/10/2026:** Codex. Hỗ trợ thêm bằng
  chứng commit JSON và kiểm tra schema enforcement thực tế trong NB1; thực thi
  lại notebook và sinh ảnh từ output đã chạy; sửa PoC sang HMAC-SHA256 và đo
  file pruning qua min/max; biên tập lại architecture brief, retention, dự
  toán và nguồn tham khảo. Các số liệu PoC mới được ghi trong
  [POC_RESULTS.md](bonus/poc/POC_RESULTS.md). Thiết kế production và các tiêu
  chí MVP được ghi rõ là giả định/mục tiêu chưa được kiểm chứng bởi PoC local.

## 2. Phạm vi và mục đích hỗ trợ
- **Thiết lập và gỡ lỗi môi trường (Environment Setup & Troubleshooting):**
  - Hỗ trợ phát hiện và xử lý lỗi tương thích đường dẫn chứa ký tự đặc biệt trên Windows (`^` trong đường dẫn người dùng) khi thư viện Rust `object_store` của `deltalake` phân tích URL, bằng cách định cấu hình `--basetemp=./.pytest_tmp` trong `pytest.ini`.
  - Hỗ trợ thiết lập kernel Jupyter (`day18`) trỏ đúng vào `.venv` để nbconvert biên dịch chính xác môi trường ảo thay vì Python toàn cục.
- **Tự động hóa thực thi (Execution Automation):**
  - Viết script chuyển đổi từ mã nguồn Jupytext `.py` sang Jupyter Notebook `.ipynb` và thực thi tuần tự từ NB1 đến NB8, đảm bảo lưu trữ toàn vẹn toàn bộ output thực tế, metadata và cell timestamps.
  - Hỗ trợ viết script trích xuất số liệu và chụp ảnh báo cáo kết quả (screenshots) hiển thị các chỉ số cốt lõi theo đúng yêu cầu của [RUBRIC.md](../docs/RUBRIC.md).
- **Hỗ trợ tổng hợp & cấu trúc tài liệu (Documentation & Architecture Review):**
  - Hỗ trợ rà soát các tiêu chí chấm điểm trong Rubric và Checkpoints.
  - Hỗ trợ xây dựng khung tài liệu thiết kế kiến trúc Lakehouse cho phần Bonus Challenge theo chuẩn Architecture Brief công nghiệp.

## 3. Cam kết tính trung thực học thuật
- **Thực thi 100% trên máy thực tế:** Mọi lệnh kiểm thử (`verify_lite.py`, `pytest`, `run_all.py`), sinh dữ liệu (`generate_data_lite.py`, `generate_ai_data.py`) và thực thi 8 notebook đều được chạy thực tế trên máy local (hệ điều hành Windows 11, Python 3.11.9, `.venv`).
- **Không ngụy tạo số liệu:** Không bỏ qua (skip) bất kỳ assertion nào, không hạ thấp ngưỡng kiểm tra (thresholds) trong rubric; toàn bộ output và screenshot phản ánh đúng kết quả thực thi của thư viện `deltalake` 1.6.6 và `pyiceberg` 0.12.0.
