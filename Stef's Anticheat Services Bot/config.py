"""
Κεντρικές ρυθμίσεις του bot.
Άλλαξε τις τιμές εδώ ανάλογα με τις ανάγκες του server σου.
"""

# ---------- Χρώματα embeds (χωρίς emoji, μόνο καθαρά μηνύματα) ----------
COLOR_INFO = 0x3498DB      # μπλε - γενικές πληροφορίες
COLOR_SUCCESS = 0x2ECC71   # πράσινο - επιτυχημένη ενέργεια
COLOR_WARNING = 0xF1C40F   # κίτρινο - προειδοποίηση
COLOR_DANGER = 0xE74C3C    # κόκκινο - ban/kick/σοβαρό περιστατικό
COLOR_RAID = 0x9B59B6      # μωβ - anti-raid events

# ---------- Anti-spam ----------
SPAM_MESSAGE_LIMIT = 5        # πόσα μηνύματα
SPAM_TIME_WINDOW = 5           # μέσα σε πόσα δευτερόλεπτα
SPAM_MUTE_DURATION = 600        # δευτερόλεπτα mute (10 λεπτά) όταν εντοπιστεί spam
MASS_MENTION_LIMIT = 5          # mentions σε ένα μήνυμα που θεωρούνται spam

# ---------- Anti-raid ----------
RAID_JOIN_LIMIT = 8            # πόσα μέλη μπαίνουν
RAID_TIME_WINDOW = 10           # μέσα σε πόσα δευτερόλεπτα -> raid mode
RAID_ACCOUNT_AGE_MIN_DAYS = 3   # λογαριασμοί νεότεροι από αυτό θεωρούνται ύποπτοι
RAID_LOCKDOWN_DURATION = 600    # δευτερόλεπτα που μένει το server σε lockdown

# ---------- Moderation ----------
MAX_WARNINGS_BEFORE_MUTE = 3    # πόσα warnings πριν αυτόματο mute
MUTE_ROLE_NAME = "Muted"        # όνομα role που χρησιμοποιείται για mute

# ---------- Logging ----------
LOG_CHANNEL_NAME = "mod-logs"   # κανάλι όπου καταγράφονται όλες οι ενέργειες

# ---------- Welcome ----------
WELCOME_CHANNEL_ID = 1517671508917485668   # κανάλι όπου στέλνεται το μήνυμα καλωσορίσματος
AUTO_ROLE_ID = 1517364646699470979          # role που δίνεται αυτόματα σε κάθε νέο μέλος

# ---------- Support Voice Channels ----------
SUPPORT_WAITING_CHANNEL_ID = 1517643757292617787   # voice κανάλι αναμονής
SUPPORT_MOVE_DELAY_SECONDS = 2                       # καθυστέρηση πριν τη μετακίνηση/δημιουργία
SUPPORT_NOTIFY_CHANNEL_ID = 1517803296490913922      # κανάλι κειμένου όπου στέλνεται η ειδοποίηση
SUPPORT_NOTIFY_ROLE_ID = 1517363787726979092          # role που γίνεται ping στην ειδοποίηση

# ---------- Status Panel ----------
STATUS_CHANNEL_ID = 1517373950739349535     # κανάλι όπου στέλνεται/ενημερώνεται το status panel
STATUS_ACTIVE_ROLE_ID = 1517363787726979092  # role που μετράμε ως "active"
STATUS_UPDATE_INTERVAL_SECONDS = 30          # κάθε πόσο ενημερώνεται αυτόματα το panel

STATUS_COLOR_ONLINE = 0x2ECC71       # πράσινο
STATUS_COLOR_MAINTENANCE = 0xF1C40F  # κίτρινο
STATUS_COLOR_OFFLINE = 0xE74C3C      # κόκκινο

STATUS_LABEL_ONLINE = "<a:38899greenloading:1517670111316676639> Online"
STATUS_LABEL_MAINTENANCE = "<a:51704orangeloading:1517670157433045163> Maintenance"
STATUS_LABEL_OFFLINE = "<a:31830redloading:1517670202693914756> Offline"

# ---------- Permissions ----------
# Ρόλοι που θεωρούνται "staff" και εξαιρούνται από anti-spam/anti-raid φίλτρα
STAFF_ROLE_NAMES = ["Admin", "Moderator", "Staff"]

# ---------- Tickets ----------
TICKET_CATEGORY_NAME = "Tickets"                # κατηγορία όπου δημιουργούνται τα κανάλια tickets
TICKET_LOG_CHANNEL_NAME = "ticket-logs"         # κανάλι όπου στέλνονται τα transcripts κλειστών tickets
TICKET_DATA_FILE = "tickets_data.json"          # αρχείο αποθήκευσης ενεργών tickets
TICKET_TRANSCRIPT_ON_CLOSE = True               # αν θα δημιουργείται transcript στο κλείσιμο

TICKET_PANEL_TITLE = "Stef's Anticheat - Support"
TICKET_PANEL_DESCRIPTION = (
    "Πάτησε το κουμπί παρακάτω για να ανοίξεις ένα ιδιωτικό ticket με το staff."
)
TICKET_PANEL_LOGO_PATH = "assets/stefs_anticheat_logo.png"   # τοπικό αρχείο εικόνας (μπαίνει σαν thumbnail)
TICKET_PANEL_LOGO_FILENAME = "stefs_anticheat_logo.png"

# Κατηγορίες tickets - εμφανίζονται σε dropdown αφού πατηθεί το κουμπί στο panel.
# emoji_id: το ID του custom emoji σου (βρίσκεις τους κωδικούς γράφοντας \:όνομα: μέσα σε Discord).
# required_role_id: αν οριστεί, ΜΟΝΟ μέλη με αυτό το role μπορούν να ανοίξουν αυτή την κατηγορία.
#                    Βάλε None για να είναι ανοιχτό σε όλους.
TICKET_CATEGORIES = [
    {
        "key": "support",
        "label": "Support Ticket",
        "description": "Technical assistance",
        "emoji_id": 1518346488479219843,
        "emoji_animated": False,
        "channel_prefix": "support",
        "required_role_id": None,
        "welcome_description": (
            "Καλώς ήρθες {mention}!\n"
            "Περίγραψε το τεχνικό πρόβλημά σου με όσο περισσότερες λεπτομέρειες μπορείς "
            "και ένα μέλος του staff θα σε βοηθήσει σύντομα."
        ),
    },
    {
        "key": "order",
        "label": "Order Ticket",
        "description": "Purchase our Anticheat",
        "emoji_id": 1518347289385631865,
        "emoji_animated": False,
        "channel_prefix": "order",
        "required_role_id": 1517635528210776264,
        "welcome_description": (
            "Καλώς ήρθες {mention}!\n"
            "Περίγραψε τι θες να αγοράσεις και ένα μέλος του staff θα σε εξυπηρετήσει σύντομα."
        ),
    },
    {
        "key": "scan",
        "label": "Scan Request",
        "description": "Request a PC Scan",
        "emoji_id": 1518347496684912660,
        "emoji_animated": False,
        "channel_prefix": "scan",
        "required_role_id": None,
        "welcome_description": (
            "Καλώς ήρθες {mention}!\n"
            "Στείλε τα στοιχεία/screenshots που χρειάζονται για το PC scan."
        ),
    },
]
