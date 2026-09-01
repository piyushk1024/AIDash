import unicodedata


def normalize_city_name(raw: str) -> str:
    """Matches the seed script's normalization exactly (to_ascii + lower).
    Both sides of the match must go through the same fold or a real match
    silently misses."""
    if not raw:
        return ""
    ascii_folded = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return ascii_folded.strip().lower()


async def match_cities(pool, rows: list[dict], x_alias: str, country: str) -> dict:
    """
    Matches each row's city-name column against geo_reference at city
    granularity. Exact-or-alias only, no fuzzy matching (see decisions.md —
    same-named-city collisions across states are an accepted gap, not
    something this function resolves).

    Mutates nothing on the input rows; returns new dicts with lat/lon and
    match_status attached. Never rejects or drops rows itself — threshold
    handling belongs to chartValidation.py, this function only reports counts.
    """
    normalized_to_rows: dict[str, list[dict]] = {}
    for row in rows:
        norm = normalize_city_name(row.get(x_alias))
        normalized_to_rows.setdefault(norm, []).append(row)

    candidate_names = [n for n in normalized_to_rows if n]

    matched_lookup: dict[str, tuple[float, float]] = {}
    if candidate_names:
        async with pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT name, lat, lon
                FROM geo_reference
                WHERE granularity = 'city'
                  AND country = $1
                  AND (name = ANY($2::text[]) OR aliases && $2::text[])
                """,
                country, candidate_names,
            )
        for r in records:
            matched_lookup[r["name"]] = (float(r["lat"]), float(r["lon"]))

    result_rows = []
    matched_count = 0
    for norm, group in normalized_to_rows.items():
        hit = matched_lookup.get(norm)
        for row in group:
            new_row = dict(row)
            if hit:
                new_row["lat"], new_row["lon"] = hit
                new_row["match_status"] = "matched"
                matched_count += 1
            else:
                new_row["match_status"] = "unmatched"
            result_rows.append(new_row)

    return {
        "rows": result_rows,
        "matched_count": matched_count,
        "total_count": len(result_rows),
    }