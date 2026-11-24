from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HandRecord:
    """One played hand: who sat at the table and each player's net result in big blinds."""
    session_id: str
    players: tuple[str, ...]
    net_bb: tuple[float, ...]
