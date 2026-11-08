import pytest

from app.util.chunk_util import split_into_chunks


def test_empty_text_returns_no_chunks():
    assert split_into_chunks("") == []
    assert split_into_chunks("   \n  ") == []


def test_short_text_returns_single_chunk():
    assert split_into_chunks("hello world", chunk_size=500, overlap=50) == ["hello world"]


def test_respects_chunk_size_upper_bound():
    text = "a" * 1000
    chunks = split_into_chunks(text, chunk_size=200, overlap=20)
    assert all(len(c) <= 200 for c in chunks)
    assert len(chunks) > 1


def test_prefers_natural_boundary_over_hard_cut():
    # 第一段恰好在 "。" 处结束，切分应该优先选在这里断开，而不是在句子中间硬切
    text = "这是第一段内容，介绍背景信息。" + "这是第二段内容，" * 20
    chunks = split_into_chunks(text, chunk_size=30, overlap=5)
    assert chunks[0].endswith("。")


def test_consecutive_chunks_overlap():
    text = "。".join(f"第{i}句话内容若干字" for i in range(30)) + "。"
    chunks = split_into_chunks(text, chunk_size=40, overlap=10)
    assert len(chunks) > 1
    # 下一个片段的开头应该能在上一个片段的尾部找到（有重叠）
    for prev, nxt in zip(chunks, chunks[1:]):
        assert prev[-10:] in prev  # sanity：overlap 长度不超过片段本身
        assert any(nxt.startswith(prev[-k:]) for k in range(1, min(10, len(prev)) + 1))


def test_full_reconstruction_without_overlap():
    # overlap=0 时，依次拼接所有片段应该能精确还原原文（只去掉了首尾空白）
    text = "第一段。\n第二段内容稍微长一点。\n第三段。"
    chunks = split_into_chunks(text, chunk_size=10, overlap=0)
    assert "".join(chunks) == text.strip()


@pytest.mark.parametrize("chunk_size,overlap", [(0, 0), (-1, 0), (10, 10), (10, 20)])
def test_invalid_params_raise(chunk_size, overlap):
    with pytest.raises(ValueError):
        split_into_chunks("some text", chunk_size=chunk_size, overlap=overlap)
