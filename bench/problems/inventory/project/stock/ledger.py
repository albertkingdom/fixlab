"""庫存帳：記每個品號現有幾件。"""


class Ledger:
    def __init__(self):
        self._units = {}

    def receive(self, sku, units):
        self._units[sku] = self._units.get(sku, 0) + units

    def on_hand(self, sku):
        return self._units.get(sku, 0)

    def skus(self):
        return sorted(self._units)
