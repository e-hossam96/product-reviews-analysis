"""Generate a synthetic reviews CSV with known ground truth.

uv run --directory backend python -m scripts.make_sample_reviews
"""

import argparse
import csv
import random
from pathlib import Path

PRODUCT_MENTIONS = [
    "The Aurora X2",
    "My Aurora X2",
    "These Aurora X2 headphones",
    "Aurora X2",
    "These headphones",
    "I bought the Aurora X2",
]

# aspect -> (sampling weight, positive sentences, negative sentences)
ASPECTS: dict[str, tuple[int, list[str], list[str]]] = {
    "battery life": (
        10,
        [
            "the battery life is fantastic, easily 30 hours",
            "battery lasts all week on a single charge",
            "battery life is amazing",
            "I barely ever have to charge them, the battery is great",
        ],
        [
            "battery life is terrible, dies after 4 hours",
            "the battery drains way too fast",
            "battery life is disappointing",
            "battery died after two weeks",
        ],
    ),
    "sound quality": (
        10,
        [
            "the sound quality is incredible, rich bass and clear highs",
            "sound is crisp and balanced",
            "audio quality is excellent for the price range",
            "the bass is deep without being muddy",
        ],
        [
            "the sound quality is flat and lifeless",
            "sound is muddy and the bass is boomy",
            "audio cuts out and sounds tinny",
            "the highs are harsh and tiring",
        ],
    ),
    "comfort": (
        8,
        [
            "super comfortable, I can wear them all day",
            "the ear cushions are soft and comfortable",
            "very lightweight and comfortable on long flights",
        ],
        [
            "they hurt my ears after an hour",
            "uncomfortable, the headband clamps too tightly",
            "the ear cups get hot and sweaty",
        ],
    ),
    "noise cancellation": (
        6,
        [
            "the noise cancellation works wonders on the train",
            "active noise cancelling blocks out the office completely",
            "noise cancellation is impressive",
        ],
        [
            "the noise cancellation barely does anything",
            "noise cancelling is weak and I still hear traffic",
            "noise cancellation adds a weird pressure feeling",
        ],
    ),
    "price": (
        6,
        [
            "great value for the price",
            "very affordable for what you get",
            "the price is unbeatable",
        ],
        [
            "too expensive for what it offers",
            "overpriced compared to the competition",
            "not worth the price",
        ],
    ),
    "bluetooth connection": (
        6,
        [
            "bluetooth pairs instantly and the connection never drops",
            "the connection is rock solid",
            "pairing took five seconds",
        ],
        [
            "the bluetooth connection keeps dropping",
            "pairing is a nightmare and it disconnects constantly",
            "connection lags behind the video",
        ],
    ),
    "microphone": (
        5,
        [
            "the microphone is clear on calls",
            "people say my voice sounds great on the mic",
            "mic quality is surprisingly good",
        ],
        [
            "the microphone is awful, everyone says I sound muffled",
            "mic picks up too much background noise",
            "microphone quality is poor on calls",
        ],
    ),
    "build quality": (
        4,
        [
            "the build quality feels premium",
            "solid construction, feels like it will last",
            "the build is sturdy and well made",
        ],
        [
            "the build quality feels cheap and plasticky",
            "the hinge snapped within a month",
            "flimsy construction, I'm afraid to bend them",
        ],
    ),
}

NO_ASPECT = [
    "Arrived two days early and nicely packaged",
    "Bought these as a gift for my brother",
    "Ordered the black one",
    "I have been using them for about a month now",
    "Shipping was quick",
    "Came in a plain box with a short manual",
]

COUNT_WEIGHTS = {0: 10, 1: 40, 2: 35, 3: 15}  # reviews mentioning k aspects
POSITIVE_SHARE = 0.6


def make_review(rng: random.Random) -> tuple[str, str]:
    k = rng.choices(list(COUNT_WEIGHTS), weights=list(COUNT_WEIGHTS.values()))[0]
    names = list(ASPECTS)
    weights = [ASPECTS[n][0] for n in names]

    chosen: list[str] = []
    while len(chosen) < k:
        pick = rng.choices(names, weights=weights)[0]
        if pick not in chosen:
            chosen.append(pick)

    parts: list[str] = []
    expected: list[str] = []
    for aspect in chosen:
        _, positive, negative = ASPECTS[aspect]
        is_positive = rng.random() < POSITIVE_SHARE
        parts.append(rng.choice(positive if is_positive else negative))
        expected.append(f"{aspect}:{'pos' if is_positive else 'neg'}")

    sentences = [p[0].upper() + p[1:] for p in parts]
    if rng.random() < 0.5 or not sentences:
        sentences.insert(0, rng.choice(PRODUCT_MENTIONS) + (" is okay" if not parts else ""))
    if rng.random() < 0.3:
        sentences.append(rng.choice(NO_ASPECT))
    rng.shuffle(sentences)  # keeps the product mention from always leading

    text = ". ".join(sentences).strip()
    if not text.endswith((".", "!")):
        text += rng.choice([".", "!"])
    return text, "|".join(expected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/sample_reviews.csv")
    parser.add_argument("--count", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "text", "expected"])
        for i in range(1, args.count + 1):
            text, expected = make_review(rng)
            writer.writerow([i, text, expected])
    print(f"wrote {args.count} reviews to {out}")


if __name__ == "__main__":
    main()
