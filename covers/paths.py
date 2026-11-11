"""Where the covers scripts find things.

WORK holds the song data and renders (downloads, stems, notes, words, builds); VENDOR holds the
outside tools and models (GAME, HubertFA, SAM, the S.A.M. UTAU bank, separation models). Both are
gitignored folders under covers/ by default; set COVERS_WORK / COVERS_VENDOR to put them elsewhere.
"""
import os

COVERS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(COVERS)
WORK = os.environ.get("COVERS_WORK", f"{COVERS}/work")
VENDOR = os.environ.get("COVERS_VENDOR", f"{COVERS}/vendor")
SHOWS = f"{REPO}/public/shows"
