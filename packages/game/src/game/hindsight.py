from hindsight_client import Hindsight

BANK_ID = "sts-v2"
HINDSIGHT_URL = "http://localhost:8888"


def create_hindsight_client() -> Hindsight:
    return Hindsight(base_url=HINDSIGHT_URL)
