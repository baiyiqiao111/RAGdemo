from typing import List, Optional

_BOUNDARY_CHARS = "\n。！？!?"
_BOUNDARY_LOOKBACK = 200  # 只在片段末尾这么长的范围内找自然边界，避免切出过短的片段


def split_into_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """把长文本切分成若干个不超过 chunk_size 字符的片段，供 RAG 向量化前使用。

    相邻片段之间保留 overlap 个字符的重叠，避免关键信息恰好落在切分点上、检索时丢失跨片段的上下文。
    切分时优先选在换行或句末标点处断开，实在找不到合适边界（如大段无标点的文本）才按 chunk_size 硬切。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须大于等于 0 且小于 chunk_size")

    text = text.strip()
    if not text:
        return []

    chunks: List[str] = []
    n = len(text)
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            boundary = _find_boundary(text, start, end)
            if boundary is not None:
                end = boundary

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= n:
            break
        start = max(end - overlap, start + 1)  # 保证每轮都向前推进，避免死循环

    return chunks


def _find_boundary(text: str, start: int, end: int) -> Optional[int]:
    """在片段末尾一小段范围内从后往前找最近的换行/句末标点，作为切分边界（标点本身归入当前片段）。"""
    search_from = max(start + 1, end - _BOUNDARY_LOOKBACK)
    for i in range(end - 1, search_from - 1, -1):
        if text[i] in _BOUNDARY_CHARS:
            return i + 1
    return None
