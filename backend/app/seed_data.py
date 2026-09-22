"""
Seed data for FOH demo database.
User emails use @gmail.com format as per specification.
Passwords are read from environment variables (see settings in config.py).
"""

# ---------------------------------------------------------------------------
# Demo users — 6 roles
# ---------------------------------------------------------------------------
DEMO_USERS = [
    {"id": "u-owner",   "name": "Alex Owner",    "email": "owner@gmail.com",   "role": "OWNER"},
    {"id": "u-manager", "name": "Morgan Manager", "email": "manager@gmail.com", "role": "MANAGER"},
    {"id": "u-host",    "name": "Hannah Host",    "email": "host@gmail.com",    "role": "HOST"},
    {"id": "u-cashier", "name": "Casey Cashier",  "email": "cashier@gmail.com", "role": "CASHIER"},
    {"id": "u-waiter",  "name": "Wade Waiter",    "email": "waiter@gmail.com",  "role": "WAITER"},
    {"id": "u-chef",    "name": "Charlie Chef",   "email": "chef@gmail.com",    "role": "CHEF"},
]

# ---------------------------------------------------------------------------
# Role → password mapping (keys match settings.{role}_password fields)
# ---------------------------------------------------------------------------
DEMO_PASSWORD_BY_ROLE = {
    "OWNER":   "owner_password",
    "MANAGER": "manager_password",
    "HOST":    "host_password",
    "CASHIER": "cashier_password",
    "WAITER":  "waiter_password",
    "CHEF":    "chef_password",
}



# ---------------------------------------------------------------------------
# Floor layout
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Floor layout — Aligned to CCTV Camera Video Data (1920×1080)
# ---------------------------------------------------------------------------
INITIAL_FLOOR = {
    "id": "floor-1",
    "name": "Main Dining",
    "width": 1050,
    "height": 640,
    "sections": [
        {
            "id": "sec-indoor",
            "name": "Indoor Dining (CCTV)",
            "color": "#818cf8",
            "bounds": {"x": 40, "y": 48, "width": 640, "height": 550},
        },
        {
            "id": "sec-bar",
            "name": "Bar Lounge",
            "color": "#fbbf24",
            "bounds": {"x": 720, "y": 48, "width": 290, "height": 260},
        },
        {
            "id": "sec-outdoor",
            "name": "Outdoor Patio",
            "color": "#38bdf8",
            "bounds": {"x": 720, "y": 330, "width": 290, "height": 268},
        },
    ],
    "labels": [
        {
            "id": "lbl-wash",
            "kind": "CUSTOM",
            "text": "Altar & Hand Wash",
            "bounds": {"x": 55, "y": 60, "width": 150, "height": 38},
        },
        {
            "id": "lbl-counter",
            "kind": "CUSTOM",
            "text": "Reception / POS",
            "bounds": {"x": 260, "y": 60, "width": 170, "height": 38},
        },
        {
            "id": "lbl-kitchen",
            "kind": "KITCHEN",
            "text": "Kitchen & Pantry",
            "bounds": {"x": 485, "y": 60, "width": 175, "height": 38},
        },
        {
            "id": "lbl-entrance",
            "kind": "ENTRANCE",
            "text": "Main Entrance",
            "bounds": {"x": 485, "y": 545, "width": 175, "height": 42},
        },
    ],
}

DEMO_CAMERA_URL = r"camera_uploads/table_t-1.mp4"

# Exact ROI regions on the CCTV camera frame (1920×1080 resolution)
_DEMO_ROIS = {
    # Table 1: Left dining table below Mandir/Altar wall
    "t-1":  {"x": 14,   "y": 440, "width": 556, "height": 380},
    # Table 2: Center dining table freestanding in middle hall
    "t-2":  {"x": 750,  "y": 250, "width": 530, "height": 360},
    # Table 3: Back-Right dining table near beverage fridge
    "t-3":  {"x": 1330, "y": 80,  "width": 440, "height": 285},
    # Table 4: Mid-Right dining table along right wall
    "t-4":  {"x": 1600, "y": 280, "width": 320, "height": 450},
    # Table 5: Foreground dining table front-center
    "t-5":  {"x": 840,  "y": 780, "width": 720, "height": 300},
    # Additional section ROIs
    "t-6":  {"x": 40,   "y": 330, "width": 140, "height": 110},
    "t-7":  {"x": 200,  "y": 340, "width": 100, "height": 100},
    "t-8":  {"x": 400,  "y": 80,  "width": 90,  "height": 90},
    "t-9":  {"x": 510,  "y": 80,  "width": 90,  "height": 90},
    "t-10": {"x": 455,  "y": 190, "width": 90,  "height": 90},
}

INITIAL_FLOOR["tables"] = [
    # ── CCTV Dining Room Tables (1 to 5) ──
    {"id": "t-1",  "sectionId": "sec-indoor",  "number": "1",  "capacity": 4, "type": "STANDARD", "shape": "RECTANGLE", "status": "AVAILABLE", "x": 80,  "y": 190, "width": 115, "height": 75, "rotation": 0, "cameraUrl": DEMO_CAMERA_URL, "roiCoords": _DEMO_ROIS["t-1"]},
    {"id": "t-2",  "sectionId": "sec-indoor",  "number": "2",  "capacity": 4, "type": "STANDARD", "shape": "RECTANGLE", "status": "AVAILABLE", "x": 270, "y": 190, "width": 125, "height": 75, "rotation": 0, "cameraUrl": DEMO_CAMERA_URL, "roiCoords": _DEMO_ROIS["t-2"]},
    {"id": "t-3",  "sectionId": "sec-indoor",  "number": "3",  "capacity": 4, "type": "STANDARD", "shape": "RECTANGLE", "status": "RESERVED",  "x": 485, "y": 140, "width": 115, "height": 75, "rotation": 0, "cameraUrl": DEMO_CAMERA_URL, "roiCoords": _DEMO_ROIS["t-3"]},
    {"id": "t-4",  "sectionId": "sec-indoor",  "number": "4",  "capacity": 4, "type": "STANDARD", "shape": "RECTANGLE", "status": "AVAILABLE", "x": 485, "y": 285, "width": 115, "height": 75, "rotation": 0, "cameraUrl": DEMO_CAMERA_URL, "roiCoords": _DEMO_ROIS["t-4"]},
    {"id": "t-5",  "sectionId": "sec-indoor",  "number": "5",  "capacity": 4, "type": "STANDARD", "shape": "RECTANGLE", "status": "AVAILABLE", "x": 270, "y": 360, "width": 135, "height": 80, "rotation": 0, "cameraUrl": DEMO_CAMERA_URL, "roiCoords": _DEMO_ROIS["t-5"]},

    # ── Bar Lounge Tables (B1 to B3) ──
    {"id": "t-8",  "sectionId": "sec-bar",     "number": "B1", "capacity": 2, "type": "BAR",      "shape": "CIRCLE",    "status": "AVAILABLE", "x": 765, "y": 120, "width": 56,  "height": 56, "rotation": 0, "cameraUrl": None,            "roiCoords": None},
    {"id": "t-9",  "sectionId": "sec-bar",     "number": "B2", "capacity": 2, "type": "BAR",      "shape": "CIRCLE",    "status": "CLEANING",  "x": 865, "y": 120, "width": 56,  "height": 56, "rotation": 0, "cameraUrl": None,            "roiCoords": None},
    {"id": "t-10", "sectionId": "sec-bar",     "number": "B3", "capacity": 2, "type": "BAR",      "shape": "CIRCLE",    "status": "AVAILABLE", "x": 815, "y": 200, "width": 56,  "height": 56, "rotation": 0, "cameraUrl": None,            "roiCoords": None},

    # ── Outdoor Patio Tables (P1, P2) ──
    {"id": "t-6",  "sectionId": "sec-outdoor", "number": "P1", "capacity": 4, "type": "STANDARD", "shape": "RECTANGLE", "status": "AVAILABLE", "x": 760, "y": 410, "width": 95,  "height": 72, "rotation": 0, "cameraUrl": None,            "roiCoords": None},
    {"id": "t-7",  "sectionId": "sec-outdoor", "number": "P2", "capacity": 2, "type": "STANDARD", "shape": "CIRCLE",    "status": "AVAILABLE", "x": 890, "y": 415, "width": 64,  "height": 64, "rotation": 0, "cameraUrl": None,            "roiCoords": None},
]

DEMO_MENU_ITEMS = [
    # ── South Indian Heritage ──
    {"name": "Ghee Roast Masala Dosa",         "description": "Crisp golden crepe roasted in A2 desi ghee with spiced potato masala & artisanal coconut chutneys", "price": 280,  "category": "South Indian",          "available": True, "display_order": 1},
    {"name": "Chettinad Spiced Chicken Sukka", "description": "Tender chicken morsels tossed in stone-ground 18-spice Chettinad masala with curry leaf crisp",     "price": 480,  "category": "South Indian",          "available": True, "display_order": 2},
    {"name": "Malabar Parotta & Mutton Curry", "description": "Flaky layered Kerala parottas paired with slow-simmered coconut, fennel & black pepper mutton gravy", "price": 580,  "category": "South Indian",          "available": True, "display_order": 3},
    {"name": "Mysore Podi Mini Idlis & Vada",  "description": "Steamed button idlis & crisp medu vada tossed in spiced gun-powder podi and organic clarified butter", "price": 240, "category": "South Indian",          "available": True, "display_order": 4},
    {"name": "Banana Leaf Meen Pollichathu",   "description": "Fresh sea bass fillet marinated in shallot-kokum paste, wrapped in banana leaf and slow pan-charred",  "price": 650,  "category": "South Indian",          "available": True, "display_order": 5},

    # ── Royal North Indian & Awadhi ──
    {"name": "Murgh Makhani (Butter Chicken)", "description": "Tandoor-smoked chicken tikka in a velvety San Marzano tomato, cashew butter and kasuri methi gravy", "price": 540,  "category": "North Indian",          "available": True, "display_order": 1},
    {"name": "Dal Bukhara / 24-Hr Dal Makhani","description": "Slow-simmered black urad lentils churned with churned white butter on overnight slow charcoal embers", "price": 420,  "category": "North Indian",          "available": True, "display_order": 2},
    {"name": "Awadhi Gosht Dum Biryani",       "description": "Fragrant long-grain aged basmati rice layered with tender mutton shank, saffron, rose water in sealed handi", "price": 680, "category": "North Indian",     "available": True, "display_order": 3},
    {"name": "Paneer Lababdar & Truffle Naan", "description": "Char-grilled cottage cheese cubes in rich onion-tomato gravy with hand-crushed whole spices & truffle naan", "price": 460, "category": "North Indian",      "available": True, "display_order": 4},
    {"name": "Royal Galouti Kebab with Sheermal","description": "Melt-in-mouth smoked lamb patties on saffron-scented mini sheermal breads with fresh mint relish",   "price": 520,  "category": "North Indian",          "available": True, "display_order": 5},

    # ── Pan-Asian & Chinese ──
    {"name": "Truffle Edamame Dim Sum (4pcs)",  "description": "Translucent steamed dumplings filled with water chestnut, shiitake mushroom & aromatic truffle oil drizzle", "price": 480, "category": "Chinese & Pan-Asian",   "available": True, "display_order": 1},
    {"name": "Kung Pao Tiger Prawns",          "description": "Wok-tossed jumbo tiger prawns with Sichuan peppers, crunchy roasted cashews, scallions & dried chillies", "price": 640, "category": "Chinese & Pan-Asian",   "available": True, "display_order": 2},
    {"name": "Hakka Chilli Garlic Noodles",     "description": "Hand-pulled artisan wheat noodles tossed with burnt garlic, bird's eye chilli and garden crisp bok choy",  "price": 380, "category": "Chinese & Pan-Asian",   "available": True, "display_order": 3},
    {"name": "Crispy Lotus Stem Honey Chilli",  "description": "Wok-glazed golden lotus root crisps with kaffir lime zest, toasted sesame and wildflower honey",          "price": 390, "category": "Chinese & Pan-Asian",   "available": True, "display_order": 4},
    {"name": "Cantonese Steamed Sea Bass",      "description": "Fresh line-caught fillet with julienned ginger, scallions, superior light soy and fragrant sesame oil",    "price": 720, "category": "Chinese & Pan-Asian",   "available": True, "display_order": 5},

    # ── Artisan Italian & Continental ──
    {"name": "Wild Forest Mushroom Risotto",    "description": "Carnaroli rice cooked with porcini broth, shaved black winter truffle, aged Parmigiano-Reggiano and thyme", "price": 580, "category": "Italian & Continental", "available": True, "display_order": 1},
    {"name": "Wood-Fired Burrata Margherita",   "description": "48-hour fermented sourdough crust, San Marzano D.O.P. sauce, artisanal fresh burrata & sweet basil",        "price": 540, "category": "Italian & Continental", "available": True, "display_order": 2},
    {"name": "Fettuccine Truffle Alfredo",      "description": "Handcrafted egg pasta in rich cultured butter, heavy cream and freshly grated winter black truffle",        "price": 490, "category": "Italian & Continental", "available": True, "display_order": 3},
    {"name": "Grilled New Zealand Lamb Chops",  "description": "Herb-crusted lamb chops with rosemary jus, garlic confit potato mash and charred tenderstem asparagus",    "price": 950, "category": "Italian & Continental", "available": True, "display_order": 4},

    # ── The Reserve Bar & Liquors / Cocktails ──
    {"name": "Smoked Rosemary Old Fashioned",   "description": "Bourbon whiskey, Angostura aromatic bitters, raw demerara syrup infused with torched organic rosemary smoke", "price": 650, "category": "Liquor & Cocktails",  "available": True, "display_order": 1},
    {"name": "Macallan 12 Single Malt (30ml)",  "description": "Highland single malt scotch whisky with notes of rich dried fruits, vanilla, oak and wood spice",          "price": 850, "category": "Liquor & Cocktails",  "available": True, "display_order": 2},
    {"name": "Royal Saffron Gin & Tonic",       "description": "Artisanal dry gin infused with Kashmiri saffron, Mediterranean tonic water and dehydrated citrus wheel",   "price": 580, "category": "Liquor & Cocktails",  "available": True, "display_order": 3},
    {"name": "Chianti Classico Riserva (Glass)","description": "Elegant Tuscan red wine with bouquet of violet, ripe cherry, French oak spice and velvety tannins",         "price": 750, "category": "Liquor & Cocktails",  "available": True, "display_order": 4},
    {"name": "Belgian Hoegaarden / Craft Beer", "description": "Chilled premium craft wheat beer with coriander and orange peel notes, served in signature chalice",         "price": 380, "category": "Liquor & Cocktails",  "available": True, "display_order": 5},

    # ── Grand Desserts ──
    {"name": "24K Gold Leaf Shahi Tukda",       "description": "Crisp saffron brioche soaked in cardamom syrup, layered with thick rabri, pistachio dust & edible gold leaf", "price": 320, "category": "Desserts",           "available": True, "display_order": 1},
    {"name": "Valrhona Warm Chocolate Fondant", "description": "Molten dark chocolate center served with handcrafted Madagascar vanilla bean gelato and berry coulis",        "price": 360, "category": "Desserts",           "available": True, "display_order": 2},
    {"name": "Classic Espresso Tiramisu",       "description": "Savoiardi ladyfingers soaked in Illy espresso, layered with whipped mascarpone and Valrhona cocoa dust",    "price": 340, "category": "Desserts",           "available": True, "display_order": 3},
]

