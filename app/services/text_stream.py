from __future__ import annotations


class ThinkingTagFilter:
    """Remove <think>...</think> even when tags cross stream chunks."""

    _OPEN = "<think>"
    _CLOSE = "</think>"

    def __init__(self) -> None:
        self._buffer = ""
        self._inside = False

    def feed(self, text: str) -> str:
        self._buffer += text
        output: list[str] = []

        while self._buffer:
            if self._inside:
                close_index = self._buffer.lower().find(self._CLOSE)
                if close_index < 0:
                    keep = len(self._CLOSE) - 1
                    if len(self._buffer) > keep:
                        self._buffer = self._buffer[-keep:]
                    break
                self._buffer = self._buffer[close_index + len(self._CLOSE) :]
                self._inside = False
                continue

            open_index = self._buffer.lower().find(self._OPEN)
            if open_index >= 0:
                output.append(self._buffer[:open_index])
                self._buffer = self._buffer[open_index + len(self._OPEN) :]
                self._inside = True
                continue

            keep = self._partial_tag_suffix_length(self._buffer, self._OPEN)
            emit_length = len(self._buffer) - keep
            if emit_length == 0:
                break
            output.append(self._buffer[:emit_length])
            self._buffer = self._buffer[emit_length:]

        return "".join(output)

    def flush(self) -> str:
        if self._inside:
            self._buffer = ""
            return ""
        output = self._buffer
        self._buffer = ""
        return output

    @staticmethod
    def _partial_tag_suffix_length(text: str, tag: str) -> int:
        lowered = text.lower()
        for length in range(min(len(text), len(tag) - 1), 0, -1):
            if lowered.endswith(tag[:length]):
                return length
        return 0


class SentenceAccumulator:
    """Turn token deltas into TTS-sized sentences with bounded latency."""

    _STRONG_ENDINGS = set("。！？!?；;\n")
    _SOFT_ENDINGS = set("，,、：:")
    _CLOSERS = set("\"'”’」』）》】")

    def __init__(self, max_chars: int = 80) -> None:
        if max_chars < 16:
            raise ValueError("max_chars must be at least 16")
        self.max_chars = max_chars
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        self._buffer += text
        sentences: list[str] = []

        while True:
            strong_index = self._first_ending(self._STRONG_ENDINGS)
            if strong_index >= 0:
                cut = strong_index + 1
                while cut < len(self._buffer) and self._buffer[cut] in (self._STRONG_ENDINGS | self._CLOSERS):
                    cut += 1
                self._append_cut(sentences, cut)
                continue

            if len(self._buffer) < self.max_chars:
                break

            search_start = max(0, self.max_chars // 2)
            soft_index = max(
                (self._buffer.rfind(char, search_start, self.max_chars + 1) for char in self._SOFT_ENDINGS),
                default=-1,
            )
            self._append_cut(sentences, soft_index + 1 if soft_index >= 0 else self.max_chars)

        return sentences

    def flush(self) -> list[str]:
        text = self._buffer.strip()
        self._buffer = ""
        return [text] if self._has_spoken_content(text) else []

    def _first_ending(self, endings: set[str]) -> int:
        positions = [self._buffer.find(char) for char in endings]
        positions = [position for position in positions if position >= 0]
        return min(positions) if positions else -1

    def _append_cut(self, sentences: list[str], cut: int) -> None:
        sentence = self._buffer[:cut].strip()
        self._buffer = self._buffer[cut:]
        if self._has_spoken_content(sentence):
            sentences.append(sentence)

    def _has_spoken_content(self, text: str) -> bool:
        punctuation = self._STRONG_ENDINGS | self._SOFT_ENDINGS | self._CLOSERS
        return bool(text) and any(not char.isspace() and char not in punctuation for char in text)
