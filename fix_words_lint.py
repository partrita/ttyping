from pathlib import Path

path = Path("src/ttyping/words.py")
content = path.read_text()

ALICE = [
    "alice", "rabbit", "hole", "wonderland", "queen", "hearts", "mad", "hatter",
    "caterpillar", "chess", "white", "cheshire", "cat", "tea", "party", "garden",
    "croquet", "duchess", "turtle", "gryphon", "dormouse", "march", "hare",
    "curious", "adventure", "shrink", "grow", "bottle", "key", "door"
]

PRIDE = [
    "elizabeth", "darcy", "bennet", "jane", "bingley", "wickham", "lydia",
    "collins", "pemberley", "netherfield", "marriage", "prejudice", "pride",
    "proposal", "sister", "fortune", "lady", "catherine", "ball", "dance",
    "letter", "reputation", "estate", "gentleman", "mother", "father",
    "wiltshire", "longbourn", "character", "manners"
]

content = content.replace(
    "ALICE: list[str] = ['alice', 'rabbit', 'hole', 'wonderland', 'queen', 'hearts', 'mad', 'hatter', 'caterpillar', 'chess', 'white', 'cheshire', 'cat', 'tea', 'party', 'garden', 'croquet', 'duchess', 'turtle', 'gryphon', 'dormouse', 'march', 'hare', 'curious', 'adventure', 'shrink', 'grow', 'bottle', 'key', 'door']",
    f"ALICE: list[str] = {ALICE}"
)

content = content.replace(
    "PRIDE: list[str] = ['elizabeth', 'darcy', 'bennet', 'jane', 'bingley', 'wickham', 'lydia', 'collins', 'pemberley', 'netherfield', 'marriage', 'prejudice', 'pride', 'proposal', 'sister', 'fortune', 'lady', 'catherine', 'ball', 'dance', 'letter', 'reputation', 'estate', 'gentleman', 'mother', 'father', 'wiltshire', 'longbourn', 'character', 'manners']",
    f"PRIDE: list[str] = {PRIDE}"
)

path.write_text(content)
