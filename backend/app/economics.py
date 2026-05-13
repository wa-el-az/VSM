from __future__ import annotations

from app.config import settings
from app.database import get_db


class EconomicsEngine:
    """Manages virtual economy faucets, sinks, and SCR monitoring."""

    def __init__(self) -> None:
        self._tax_rates = {
            "buy": settings.tax_buy_rate,
            "sell": settings.tax_sell_rate,
            "limit": settings.tax_limit_rate,
            "transfer": settings.tax_transfer_rate,
            "withdrawal": settings.tax_withdrawal_rate,
        }

    @property
    def tax_rates(self) -> dict[str, float]:
        return dict(self._tax_rates)

    def calculate_tax(self, amount: float, tx_type: str) -> float:
        rate = self._tax_rates.get(tx_type, 0.005)
        return round(amount * rate, 2)

    def apply_trade_tax(
        self, conn, user_id: int, gross_amount: float, tx_type: str
    ) -> tuple[float, float]:
        """Deduct tax from a trade. Returns (net_amount, tax_amount)."""
        tax = self.calculate_tax(gross_amount, tx_type)
        net = gross_amount - tax

        conn.execute(
            "UPDATE users SET total_taxed = total_taxed + ? WHERE id = ?",
            (tax, user_id),
        )
        conn.execute(
            "INSERT INTO ledger_entries (user_id, entry_type, amount, balance_after, description) "
            "VALUES (?, 'tax', ?, (SELECT balance FROM users WHERE id = ?), ?)",
            (user_id, -tax, user_id, f"Transaction tax ({tx_type}): {tax}"),
        )

        return net, tax

    def credit_faucet(self, conn, user_id: int, amount: float, description: str) -> float:
        """Credit PoW reward to player. Returns new balance."""
        conn.execute(
            "UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE id = ?",
            (amount, amount, user_id),
        )
        row = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        new_balance = row["balance"]

        conn.execute(
            "INSERT INTO ledger_entries (user_id, entry_type, amount, balance_after, description) "
            "VALUES (?, 'faucet', ?, ?, ?)",
            (user_id, amount, new_balance, description),
        )

        return new_balance

    def get_scr(self) -> float:
        """Calculate current Sink Coverage Ratio."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(total_taxed), 0) AS sinks, "
                "COALESCE(SUM(total_earned), 0) AS faucets FROM users"
            ).fetchone()

        faucets = row["faucets"]
        sinks = row["sinks"]
        if faucets == 0:
            return 1.0
        return sinks / faucets

    def auto_adjust_rates(self) -> None:
        """If SCR falls below floor, increase all tax rates."""
        scr = self.get_scr()
        if scr < settings.scr_floor:
            step = settings.scr_adjustment_step
            self._tax_rates = {k: v + step for k, v in self._tax_rates.items()}

    def get_economy_stats(self) -> dict:
        with get_db() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(balance), 0) AS supply, "
                "COALESCE(SUM(total_earned), 0) AS faucets, "
                "COALESCE(SUM(total_taxed), 0) AS sinks, "
                "COUNT(*) AS players FROM users"
            ).fetchone()

        faucets = row["faucets"]
        sinks = row["sinks"]
        scr = sinks / faucets if faucets > 0 else 1.0

        return {
            "total_supply": round(row["supply"], 2),
            "total_faucet_output": round(faucets, 2),
            "total_sink_drainage": round(sinks, 2),
            "sink_coverage_ratio": round(scr, 4),
            "active_players": row["players"],
            "current_tax_rates": self.tax_rates,
        }


economics = EconomicsEngine()
