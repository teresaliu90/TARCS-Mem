from datetime import date

from tarcsmem.ui import resolve_business_date


def test_resolve_business_date_accepts_exact_chinese_and_iso_dates() -> None:
    assert resolve_business_date("2026年9月12日深圳展会住宿标准")[0] == date(2026, 9, 12)
    assert resolve_business_date("2026-08-15 折扣上限")[0] == date(2026, 8, 15)


def test_resolve_business_date_handles_month_and_fallback() -> None:
    assert resolve_business_date("2026年5月华南区折扣")[0] == date(2026, 5, 1)
    assert resolve_business_date("当前折扣是多少？", fallback=date(2026, 7, 23))[0] == date(
        2026, 7, 23
    )
