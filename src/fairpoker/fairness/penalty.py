"""Site-side fairness penalty: winners at unfair tables give part of their profit back."""
from fairpoker.hands.records import HandRecord


def apply_fairness_penalty(record: HandRecord, fairness: float, rate: float) -> HandRecord:
    """Move rate * (1 - fairness/100) of each winner's profit to that hand's losers, by share of losses.

    Chips are conserved: the hand still sums to zero. A perfectly fair table pays nothing.
    """
    levy = rate * (1.0 - fairness / 100.0)
    total_lost = -sum(net for net in record.net_bb if net < 0)
    if levy <= 0 or total_lost == 0:
        return record
    pool = levy * sum(net for net in record.net_bb if net > 0)
    adjusted = tuple(_adjust_net(net, levy, pool, total_lost) for net in record.net_bb)
    return HandRecord(session_id=record.session_id, players=record.players, net_bb=adjusted)


def _adjust_net(net: float, levy: float, pool: float, total_lost: float) -> float:
    if net > 0:
        return net * (1 - levy)
    if net < 0:
        return net + pool * (-net / total_lost)
    return net
