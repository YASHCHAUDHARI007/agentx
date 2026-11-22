"""Vocabularies for the request parser.

Catalogue values (categories, colours, brands, sizes) are read from catalogue.csv once, offline,
which the README allows ("read catalogue.csv as much as you like to build vocabularies").
Everything else here is general shopping language, English and Hindi-English, written by hand.
"""
import csv
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "starter_kit" / "ps1-anticipatory-commerce"
CATALOGUE = KIT / "catalogue.csv"

# ---------------------------------------------------------------- categories
# Phrase -> catalogue category. Multi-word phrases win over their parts (longest match).
CATEGORY_SYNONYMS = {
    "running shoes": ["running shoe", "running shoes", "runners", "runner", "jogging shoes", "jogging shoe",
                      "running sneakers", "running sneaker", "running trainers", "running trainer", "sports shoes", "sport shoes", "trail shoes",
                      "trail running shoes", "marathon shoes", "training shoes"],
    "sneakers": ["sneakers", "sneaker", "casual shoes", "casual shoe", "casual sneakers", "casual sneaker",
                 "kicks", "canvas shoes", "lifestyle shoes", "street shoes"],
    "sandals": ["sandals", "sandal", "slides", "slide", "floaters", "floater", "flip flops", "flip flop",
                "flipflops", "slippers", "slipper", "chappals", "chappal", "sliders"],
    "t-shirts": ["t-shirts", "t-shirt", "t shirts", "t shirt", "tshirts", "tshirt", "tees", "tee",
                 "polo tee", "round neck tee", "tee shirt", "tee shirts"],
    "shirts": ["shirts", "shirt", "casual shirt", "formal shirt", "button down", "button-down"],
    "jeans": ["jeans", "jean", "pair of jeans", "denims", "denim", "denim jeans"],
    "dresses": ["dresses", "dress", "sundress", "sun dress", "frock", "gown", "one piece", "one-piece"],
    "kurtas": ["kurtas", "kurta", "kurti", "kurtis"],
    "hoodies": ["hoodies", "hoodie", "hoody", "hooded sweatshirt", "hooded sweatshirts", "sweatshirt", "sweatshirts",
                "hooded jacket"],
    "jackets": ["jackets", "jacket", "bomber", "bomber jacket", "windcheater", "puffer", "puffer jacket"],
    "track pants": ["track pants", "track pant", "trackpants", "trackpant", "joggers", "jogger",
                    "jogging pants", "sweatpants", "sweat pants", "jogger pants", "track bottoms",
                    "trackies"],
    "backpacks": ["backpacks", "backpack", "bag pack", "bagpack", "back pack", "rucksack", "rucksacks", "school bag",
                  "laptop bag", "college bag", "bag", "bags", "daypack"],
    "caps": ["caps", "cap", "baseball cap", "hat", "hats", "topi"],
    "headphones": ["headphones", "headphone", "headset", "headsets", "earphones", "earphone",
                   "over ear headphones", "on ear headphones"],
    "watches": ["watches", "watch", "wrist watch", "wristwatch", "wrist watches", "ghadi", "analog watch"],
    "wallets": ["wallets", "wallet", "purse", "billfold", "card holder"],
}

# ---------------------------------------------------------------- colours
COLOUR_SYNONYMS = {
    "black": ["black", "blk", "kaala", "kala", "kaali", "kali", "kaale", "kale", "jet black"],
    "navy": ["navy", "navy blue", "dark blue", "midnight blue"],
    "grey": ["grey", "gray", "charcoal", "ash", "slate", "dark grey", "dark gray", "light grey", "light gray",
             "sleti"],
    "blue": ["blue", "neela", "nila", "neeli", "nili", "neele", "nile", "sky blue", "royal blue", "light blue"],
    "white": ["white", "safed", "safaid", "safedi", "off white", "off-white"],
    "olive": ["olive", "olive green", "khaki green", "army green", "military green"],
    "red": ["red", "laal", "lal", "crimson"],
    "maroon": ["maroon", "burgundy", "wine", "wine red"],
    "green": ["green", "hara", "hari", "hare", "dark green", "bottle green"],
    "beige": ["beige", "cream", "khaki", "sand", "off cream"],
    "brown": ["brown", "bhura", "bhoora", "bhuri", "bhure", "chocolate", "coffee"],
    "yellow": ["yellow", "peela", "pila", "peeli", "pili", "peele", "mustard"],
    "pink": ["pink", "gulabi", "baby pink"],
    "tan": ["tan", "camel"],
    "gold": ["gold", "golden", "sunehra", "sunhera"],
    "silver": ["silver", "chandi", "silvery"],
}

# ---------------------------------------------------------------- sizes
# Letter sizes as words. Single uppercase letters (S, M, L) are handled in the parser, since
# lowercase "s"/"m"/"l" are too risky.
SIZE_WORDS = {
    "XS": ["xs", "extra small", "x small", "x-small", "extra-small"],
    "S": ["small", "smol", "sml"],
    "M": ["medium", "med"],
    "L": ["large", "lrg", "lg"],
    "XL": ["xl", "extra large", "x large", "x-large", "extra-large"],
    "XXL": ["xxl", "2xl", "double xl", "double extra large", "extra extra large", "xx large", "xx-large",
            "double x l", "xx-large"],
}

# Words that introduce a size number ("size 9", "UK 9", "waist 32", "das number").
SIZE_CUES = {"size", "uk", "waist", "number", "no.", "sz", "shoe size"}
SIZE_POST_CUES = {"uk", "waist", "size", "number", "no."}

# ---------------------------------------------------------------- numbers
UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
         "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
         "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
# Hindi number words (romanised). "ek" and "do" are left out: "do you have" is far more common.
HINDI_UNITS = {"teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "che": 6, "saat": 7,
               "aath": 8, "nau": 9, "das": 10, "gyarah": 11, "barah": 12, "baarah": 12, "pandrah": 15,
               "pandra": 15, "solah": 16, "satrah": 17, "satra": 17, "athara": 18, "atharah": 18,
               "unnees": 19, "bees": 20, "pachchees": 25, "pachees": 25, "tees": 30, "chalees": 40,
               "pachaas": 50}
HINDI_FRACTIONS = {"dhai": 2.5, "dedh": 1.5, "dhaai": 2.5, "dedhh": 1.5}
HALF_MORE = {"saadhe", "sadhe", "saade"}          # "saadhe teen hazaar" = 3,500
MULTIPLIERS = {"hundred": 100, "sau": 100, "thousand": 1000, "hazaar": 1000, "hazar": 1000, "hajar": 1000,
               "grand": 1000, "k": 1000, "lakh": 100000}
CURRENCY = {"rs", "rs.", "₹", "inr", "rupees", "rupee", "bucks"}

# ---------------------------------------------------------------- function words
# Budget words, correction words and filler. Used to tell "known" words from unknown ones:
# an unknown content word makes the agent more careful about committing early.
BUDGET_CUES = {"under", "below", "less", "than", "within", "max", "maximum", "up", "to", "upto", "budget",
               "not", "more", "tak", "se", "kam", "ke", "andar", "andar,", "around", "about", "price",
               "range", "cheaper", "at", "most", "only", "for", "of", "no", "over"}
CORRECTION_CUES = {"no", "wait", "sorry", "oops", "actually", "mean", "meant", "rather", "instead", "change",
                   "make", "nahi", "nahin", "matlab", "galti", "scratch", "correction", "second", "thought", "bad",
                   "mistake", "rephrase", "let", "wrong", "nope"}
FILLER = set("""
a an the i i'm i'd im id me my mine we you your yours do does did have has had any some it it's its is are
was be been am want wanted need needed looking look find get show give see like love would could can please
pls plz thanks thank thx hi hey hello hii in on by from with and or but also oh ok okay so just that this
these those there here for to of as at if what which one something thing things buy buying purchase order
brand brands colour color colours colors size sizes pair pairs nothing too flashy fancy simple plain gift
gifting wedding office gym party dad mom mum brother sister wife husband friend son daughter father mother
myself him her them his their week today tomorrow soon need it this kind type style sure make it's let's um
uh hmm er erm like yeah yes good nice great well really very quite bit little else something anything
mujhe mere liye chahiye chaiye kya aapke aap paas hai hain milega milegi dikhao dikhaiye dikha bhaiya bhai
na ka ki ke wala wali wale aur haan ek baat bhi se mein me main ko please ji thoda sa yeh ye woh wo kuch
koi accha acha zara kaun sa
casual formal regular new latest stylish comfortable comfy cool trendy best good quality available
stock have got
help suggest suggestion guys searching search chance possible should say said forgot btw p.s ps asap cheers ty
daily use college trip birthday everyday rang shade tone coloured colored color-wise wala neeche
""".split())

# Words that sharpen a colour without changing it ("jet black", "bright red", "heather grey").
COLOUR_MODIFIERS = {"jet", "pitch", "all", "bright", "deep", "dark", "light", "pure", "snow", "hot", "cherry", "lemon",
                    "emerald", "forest", "heather", "ash", "steel", "chocolate", "pale", "bold", "neon", "matte",
                    "shiny", "muted", "soft", "rich", "dull", "solid"}

# Generic product words. Used only when nothing more specific names the category.
GENERIC_HEADS = {"shoes": "footwear", "shoe": "footwear", "trainers": "footwear", "trainer": "footwear",
                 "footwear": "footwear", "pants": "pants", "pant": "pants", "bottoms": "pants", "trousers": "pants"}
