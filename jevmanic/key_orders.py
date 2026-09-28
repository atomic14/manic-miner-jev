"""The optimum key order of each cavern, for `--key-order optimum`.

The letters are the key letters on the key decision's map. Here the cavern
numbers start at 0. The optimum order is a good reference order, not a
proven best order.
"""

OPTIMUM_KEY_ORDER = {
    0: "EACDB",  # Central Cavern
    1: "EDABC",  # The Cold Room
    2: "EABCD",  # The Menagerie
    3: "DEABC",  # Abandoned Uranium Workings
    4: "ABDCE",  # Eugene's Lair
    5: "ABCED",  # Processing Plant
    6: "BCAED",  # The Vat
    7: "BCAD",  # Miner Willy meets the Kong Beast
    8: "A",  # Wacky Amoebatrons
    9: "BCDEA",  # The Endorian Forest
    10: "ABEDC",  # Attack of the Mutant Telephones
    11: "CADEB",  # Return of the Alien Kong Beast
    12: "EBCDA",  # Ore Refinery
    13: "BDAC",  # Skylab Landing Bay
    14: "CBA",  # The Bank
    15: "DCAB",  # The Sixteenth Cavern
    16: "BADCE",  # The Warehouse
    17: "A",  # Amoebatrons' Revenge
    18: "CAB",  # Solar Power Generator
    19: "EDCAB",  # The Final Barrier
}

OPTIMUM = "OPTIMUM"  # the `forced_key_order` value that selects the order above
