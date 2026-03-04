from pathlib import Path

path = Path("src/ttyping/words.py")
content = path.read_text()

ALICE_STR = """ALICE: list[str] = [
    "alice", "rabbit", "hole", "wonderland", "queen", "hearts", "mad", "hatter",
    "caterpillar", "chess", "white", "cheshire", "cat", "tea", "party", "garden",
    "croquet", "duchess", "turtle", "gryphon", "dormouse", "march", "hare",
    "curious", "adventure", "shrink", "grow", "bottle", "key", "door",
]"""

PRIDE_STR = """PRIDE: list[str] = [
    "elizabeth", "darcy", "bennet", "jane", "bingley", "wickham", "lydia",
    "collins", "pemberley", "netherfield", "marriage", "prejudice", "pride",
    "proposal", "sister", "fortune", "lady", "catherine", "ball", "dance",
    "letter", "reputation", "estate", "gentleman", "mother", "father",
    "wiltshire", "longbourn", "character", "manners",
]"""

import re
content = re.sub(r"ALICE: list\[str\] = \[.*?\]", ALICE_STR, content, flags=re.DOTALL)
content = re.sub(r"PRIDE: list\[str\] = \[.*?\]", PRIDE_STR, content, flags=re.DOTALL)

path.write_text(content)
