import re
import html

class InputSanitizer:
    # Pattern cho Email
    EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    # Pattern cho Số điện thoại Việt Nam (10 số, bắt đầu bằng 0 hoặc +84)
    PHONE_PATTERN = re.compile(r'(\+84|0)[3|5|7|8|9][0-9]{8}\b')
    # Pattern loại bỏ thẻ HTML đơn giản
    HTML_TAG_PATTERN = re.compile(r'<[^>]*>')

    @classmethod
    def sanitize_xss(cls, text: str) -> str:
        """Loại bỏ thẻ HTML và escape các ký tự đặc biệt."""
        if not text:
            return ""
        # Xóa các thẻ HTML
        text_no_tags = cls.HTML_TAG_PATTERN.sub('', text)
        # Chuyển đổi các ký tự <, >, &, " thành dạng an toàn (escape)
        safe_text = html.escape(text_no_tags)
        return safe_text

    @classmethod
    def mask_pii(cls, text: str) -> str:
        """Che giấu Email và Số điện thoại."""
        if not text:
            return ""
        # Che email thành ***@***.com
        text = cls.EMAIL_PATTERN.sub('[EMAIL_MASKED]', text)
        # Che số điện thoại
        text = cls.PHONE_PATTERN.sub('[PHONE_MASKED]', text)
        return text

    @classmethod
    def process(cls, text: str) -> str:
        """Thực hiện toàn bộ quy trình làm sạch."""
        text = cls.sanitize_xss(text)
        text = cls.mask_pii(text)
        return text.strip()