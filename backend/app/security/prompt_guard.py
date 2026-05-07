import re
from fastapi import HTTPException
from .sanitizer import InputSanitizer

class PromptGuard:
    # Danh sách các từ khóa/pattern thường dùng để tấn công Prompt Injection
    INJECTION_PATTERNS = [
        r"(?i)\b(ignore|bỏ qua|quên)\s+(tất cả|all)?\s*(lệnh|instructions|prompt)\b",
        r"(?i)\b(system prompt|hướng dẫn hệ thống)\b",
        r"(?i)\b(jailbreak|bypass|hack)\b",
        r"(?i)\b(đóng vai|act as)\b.*\b(hacker|bad|evil)\b",
        r"(?i)\b(in ra|print|show)\s+(tất cả|all)?\s*(prompt|instructions)\b"
    ]
    
    _compiled_patterns = [re.compile(p) for p in INJECTION_PATTERNS]

    @classmethod
    def check_injection(cls, text: str) -> bool:
        """
        Kiểm tra xem văn bản có chứa mẫu tấn công hay không.
        Trả về True nếu phát hiện nghi vấn, False nếu an toàn.
        """
        for pattern in cls._compiled_patterns:
            if pattern.search(text):
                return True
        return False

    @classmethod
    def verify_and_clean(cls, raw_query: str) -> str:
        """
        Hàm chính được gọi từ Router.
        Thực hiện: Mask PII, chống XSS -> Check Injection -> Trả về câu hỏi sạch.
        """
        # Bước 1 & 2: Làm sạch dữ liệu (XSS & PII)
        clean_query = InputSanitizer.process(raw_query)

        # Bước 3: Kiểm tra Prompt Injection
        is_malicious = cls.check_injection(clean_query)
        if is_malicious:
            # Nếu phát hiện tấn công, ném lỗi 403 Forbidden chặn ngay ở cổng API
            raise HTTPException(
                status_code=403, 
                detail="Lỗi Bảo Mật: Câu hỏi của bạn chứa nội dung vi phạm chính sách hệ thống."
            )

        # Trả về câu hỏi đã được làm sạch và an toàn
        return clean_query