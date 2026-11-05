import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator

from app.models import NgramCount

# English only. Replace or extend for other languages.
STOPWORDS = frozenset(
    [
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "can't",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he'd",
        "he'll",
        "he's",
        "her",
        "here",
        "here's",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "how's",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "let's",
        "me",
        "more",
        "most",
        "mustn't",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "she'd",
        "she'll",
        "she's",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "that's",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "there's",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "were",
        "weren't",
        "what",
        "what's",
        "when",
        "when's",
        "where",
        "where's",
        "which",
        "while",
        "who",
        "who's",
        "whom",
        "why",
        "why's",
        "will",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "also",
        "just",
        "really",
        "get",
        "got",
        "one",
        "even",
        "still",
        "much",
        "many",
        "well",
    ]
)

_SEGMENT_SPLIT_RE = re.compile(r"[^\w\s'-]+")  # punctuation ends a segment
_TOKEN_RE = re.compile(r"[^\W_]+(?:['-][^\W_]+)*")
_CANDIDATE_FACTOR = 5  # consider top_k * 5 candidates before removing redundant ones


def _segments(text: str) -> Iterator[list[str]]:
    text = text.lower().replace("’", "'")
    for segment in _SEGMENT_SPLIT_RE.split(text):
        tokens = _TOKEN_RE.findall(segment)
        if tokens:
            yield tokens


def _is_edge_ok(token: str) -> bool:
    return token not in STOPWORDS and (len(token) >= 2 or token.isdigit())


def _is_valid(gram: list[str]) -> bool:
    if not (_is_edge_ok(gram[0]) and _is_edge_ok(gram[-1])):
        return False
    return not (len(gram) == 1 and gram[0].isdigit())


def count_ngrams(texts: Iterable[str], max_n: int) -> Counter[str]:
    """Number of reviews containing each n-gram (not total occurrences)."""
    counts: Counter[str] = Counter()
    for text in texts:
        seen: set[str] = set()
        for tokens in _segments(text):
            for n in range(1, max_n + 1):
                for i in range(len(tokens) - n + 1):
                    gram = tokens[i : i + n]
                    if _is_valid(gram):
                        seen.add(" ".join(gram))
        counts.update(seen)
    return counts


def top_ngrams(
    texts: Iterable[str],
    *,
    max_n: int = 3,
    top_k: int = 100,
    min_count: int = 2,
) -> list[NgramCount]:
    counts = count_ngrams(texts, max_n)
    candidates = [(gram, c, gram.count(" ") + 1) for gram, c in counts.items() if c >= min_count]
    candidates.sort(key=lambda t: (-t[1], -t[2], t[0]))  # count, longer, alphabetical
    window = candidates[: top_k * _CANDIDATE_FACTOR]

    by_count: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for gram, c, n in window:
        by_count[c].append((f" {gram} ", n))

    result: list[NgramCount] = []
    for gram, c, n in window:
        padded = f" {gram} "
        # drop a phrase that sits inside a longer one with the same review count
        if any(other_n > n and padded in other for other, other_n in by_count[c]):
            continue
        result.append(NgramCount(ngram=gram, count=c))
        if len(result) == top_k:
            break
    return result
