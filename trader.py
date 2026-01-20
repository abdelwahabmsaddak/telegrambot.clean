# trader.py
from dataclasses import dataclass

@dataclass
class PaperTrade:
    asset: str
    side: str
    reason: str
    status: str = "OPEN"

class Trader:
    # Paper only by default
    def __init__(self):
        self.paper_positions = {}  # uid -> PaperTrade

    def open_paper(self, uid: int, asset: str, side: str, reason: str) -> PaperTrade:
        tr = PaperTrade(asset=asset, side=side, reason=reason)
        self.paper_positions[uid] = tr
        return tr

    def close_paper(self, uid: int):
        tr = self.paper_positions.get(uid)
        if not tr:
            return None
        tr.status = "CLOSED"
        return tr

    def status(self, uid: int):
        return self.paper_positions.get(uid)
