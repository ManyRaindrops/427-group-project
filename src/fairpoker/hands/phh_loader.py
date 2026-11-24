"""Read no-limit hold'em hands straight out of the PHH dataset zip with pokerkit."""
import zipfile
from pathlib import Path, PurePosixPath

from pokerkit import HandHistory

from fairpoker.hands.records import HandRecord

NO_LIMIT_HOLDEM_VARIANT = "NT"  # PHH variant code for no-limit Texas hold'em


def parse_hand_record(text: str, session_id: str) -> HandRecord | None:
    """Parse one .phh document. Returns None for other variants or hands without final stacks."""
    history = HandHistory.loads(text)
    if history.variant != NO_LIMIT_HOLDEM_VARIANT or history.finishing_stacks is None or history.players is None:
        return None
    big_blind = float(max(history.blinds_or_straddles))
    net = tuple(float(end - start) / big_blind for start, end in zip(history.starting_stacks, history.finishing_stacks))
    return HandRecord(session_id=session_id, players=tuple(history.players), net_bb=net)


def load_zip_dataset(zip_path: Path, prefix: str) -> list[HandRecord]:
    """Load every NLHE hand under `prefix` in the zip. The parent folder name is the session id."""
    records: list[HandRecord] = []
    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if name.startswith(prefix) and name.endswith(".phh"))
        for name in names:
            record = parse_hand_record(archive.read(name).decode("utf-8"), PurePosixPath(name).parent.name)
            if record is not None:
                records.append(record)
    return records
