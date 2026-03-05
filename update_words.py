from pathlib import Path

path = Path("src/ttyping/words.py")
content = path.read_text()

ALICE = [
    "alice", "rabbit", "hole", "wonderland", "queen", "hearts", "mad", "hatter", "caterpillar", "chess",
    "white", "cheshire", "cat", "tea", "party", "garden", "croquet", "duchess", "turtle", "gryphon",
    "dormouse", "march", "hare", "curious", "adventure", "shrink", "grow", "bottle", "key", "door"
]

PRIDE = [
    "elizabeth", "darcy", "bennet", "jane", "bingley", "wickham", "lydia", "collins", "pemberley", "netherfield",
    "marriage", "prejudice", "pride", "proposal", "sister", "fortune", "lady", "catherine", "ball", "dance",
    "letter", "reputation", "estate", "gentleman", "mother", "father", "wiltshire", "longbourn", "character", "manners"
]

new_lists = f"""
ALICE: list[str] = {ALICE}

PRIDE: list[str] = {PRIDE}
"""

# Insert before get_words
content = content.replace("def get_words(", new_lists + "\n\ndef get_words(")

# Update get_words
old_get_words = """def get_words(lang: str = "en", count: int = 25) -> list[str]:
    \"\"\"Return a random selection of words for the given language.\"\"\"
    source = ENGLISH if lang == "en" else KOREAN
    # Use random.choices for better performance on large counts if needed,
    # though random.choice in a loop is fine for small counts.
    return random.choices(source, k=count)"""

new_get_words = """def get_words(lang: str = "en", count: int = 25) -> list[str]:
    \"\"\"Return a random selection of words for the given language or book.\"\"\"
    sources = {
        "en": ENGLISH,
        "ko": KOREAN,
        "alice": ALICE,
        "pride": PRIDE
    }
    source = sources.get(lang, ENGLISH)
    return random.choices(source, k=count)"""

content = content.replace(old_get_words, new_get_words)

path.write_text(content)
