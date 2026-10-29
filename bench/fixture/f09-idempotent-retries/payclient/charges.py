def create_charge(client, amount_minor: int, currency: str) -> dict:
    return client.request("POST", "/charges", {}, {"amount": amount_minor, "currency": currency})


def get_charge(client, charge_id: str) -> dict:
    return client.request("GET", f"/charges/{charge_id}")
