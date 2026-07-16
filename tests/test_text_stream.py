from app.services.text_stream import SentenceAccumulator, ThinkingTagFilter


def test_thinking_filter_removes_tags_split_across_chunks():
    stream_filter = ThinkingTagFilter()
    chunks = ["开头<th", "ink>内部推理", "</thi", "nk>最终", "回答。"]
    output = "".join(stream_filter.feed(chunk) for chunk in chunks) + stream_filter.flush()

    assert output == "开头最终回答。"


def test_sentence_accumulator_emits_punctuation_and_flushes_tail():
    accumulator = SentenceAccumulator(max_chars=24)

    assert accumulator.feed("第一句话。第二句话") == ["第一句话。"]
    assert accumulator.feed("！尾巴") == ["第二句话！"]
    assert accumulator.flush() == ["尾巴"]


def test_sentence_accumulator_bounds_long_text_at_soft_punctuation():
    accumulator = SentenceAccumulator(max_chars=20)
    sentences = accumulator.feed("一二三四五六七八九十，十一十二十三十四十五十六")
    sentences.extend(accumulator.flush())

    assert "".join(sentences) == "一二三四五六七八九十，十一十二十三十四十五十六"
    assert all(len(sentence) <= 20 for sentence in sentences)


def test_sentence_accumulator_keeps_consecutive_endings_and_drops_punctuation_only():
    accumulator = SentenceAccumulator(max_chars=24)

    assert accumulator.feed("真的吗？！当然。") == ["真的吗？！", "当然。"]
    assert accumulator.feed("！！！\n") == []
    assert accumulator.flush() == []
