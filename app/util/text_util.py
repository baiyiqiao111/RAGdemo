import hashlib
import re
from typing import Tuple


def content_meta(content: str) -> Tuple[int, str]:
    """返回 (字数, 内容哈希)。字数按非空白字符计，与语雀的统计方式接近。"""
    word_count = len(re.sub(r"\s", "", content))
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return word_count, content_hash
