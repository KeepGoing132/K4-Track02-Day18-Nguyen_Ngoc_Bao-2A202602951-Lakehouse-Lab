# Reflection — Lakehouse Anti-Patterns

Hệ thống RAG và AI Agent tôi quan tâm dễ vướng **Anti-Pattern: "The Stale External Index / Lifecycle Skew"** (đồng bộ bất đối xứng giữa Lakehouse và Vector DB ngoài).

**Nguyên nhân:** Khi tách rời Lakehouse (System of Record) và Vector DB (Milvus/Pinecone), pipeline sync thường chỉ làm một chiều dạng batch upsert. Khi người dùng thực thi quyền xóa dữ liệu cá nhân (Right-to-be-Forgotten theo Nghị định 13/2023/NĐ-CP hoặc GDPR), dữ liệu bị xóa khỏi bảng Delta nhưng vector vẫn tồn tại vĩnh viễn trong external index, khiến LLM tiếp tục truy xuất dữ liệu nhạy cảm đã bị thu hồi.

**Cách phòng tránh:**
1. **In-Table Vectors:** Lưu embeddings trực tiếp trong cột Parquet và truy vấn SQL (`array_cosine_similarity`) cho phân tích/offline RAG để vòng đời vector gắn liền với bản ghi gốc.
2. **Change Data Feed (CDF):** Nếu dùng Vector DB ngoài cho serving online sub-50ms, bắt buộc xây dựng streaming pipeline lắng nghe sự kiện DELETE qua Delta CDF để đồng bộ thu hồi vector ngay lập tức.

*(Phạm vi dùng AI khai báo tại [AI_USAGE.md](AI_USAGE.md)).*
