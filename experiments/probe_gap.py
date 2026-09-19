"""Test: can jev see the size of a gap in a map row?

The state is one map row: Willy, then N empty cells, then a nasty. The
question asks if the gap is exactly 2 cells. The script compares three
forms of the same fact: a map row, a packed map row, and a number.

Run:  uv run python -m experiments.probe_gap
"""

from dotenv import load_dotenv
from typesafe_sdk import Noul, TypeSafeClient

QUESTION = {
    "gap2": Noul(
        instructions=(
            "Are there exactly 2 empty cells between Willy and the nasty? "
            "In a map row, W is Willy, X is the nasty, and '.' is one empty cell."
        )
    )
}


def main():
    load_dotenv(".env")
    client = TypeSafeClient()
    print(f"{'gap':>4} {'spaced row':>12} {'packed row':>12} {'number':>8}   (probability of yes; correct = high only at gap 2)")
    for gap in range(0, 7):
        spaced = "W W " + ". " * gap + "X . ."
        packed = "WW" + "." * gap + "X.."
        states = [{"row": spaced}, {"row": packed}, {"empty_cells_between_willy_and_nasty": gap}]
        probs = [client.system_one(s, QUESTION).nouls["gap2"].noul for s in states]
        print(f"{gap:>4} {probs[0]:>12.2f} {probs[1]:>12.2f} {probs[2]:>8.2f}")


if __name__ == "__main__":
    main()
