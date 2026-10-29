def transform(r: dict) -> dict:
    first, last = r["name"].split(" ", 1)
    return {"schema_version": 2, "id": r["id"], "given_name": first, "family_name": last,
            "email": r["email"], "phone": r["phone"], "signup_date": r["signup"], "updated_at": r["updated_at"]}
