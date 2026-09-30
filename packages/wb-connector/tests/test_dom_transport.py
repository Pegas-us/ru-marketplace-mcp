"""WB_TRANSPORT=dom: page parsing and the render/stop contract, all offline.

Fixture text is what the 2026-09-30 live session read in the scraping-profile
Chrome (search «UPD2018», product nm 1345073040), split into the lines
``innerText`` yields. One tile is also given flattened onto a single line, the
shape a layout change would produce, to prove parsing does not depend on the
line breaks.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastmcp.exceptions import ToolError
from wb_connector import dom_transport as D
from wb_connector import server

SEARCH_PAYLOAD = {
    "title": "Интернет\u2011магазин Wildberries: широкий ассортимент товаров - ",
    "tiles": [
        {
            # verbatim from wb_dom_diag.py, 2026-09-30 (server-opened tab)
            "nm": "1517577386",
            "lines": [
                "−6%",
                "4 486 ₽",
                "4 897 ₽",
                "с WB Кошельком",
                "QULE",
                "/",
                "Адаптер DP USB3.1 Gen2 UPD2018",
                "5",
                "· 1 оценка",
                "11 октября",
            ],
            "label": "Адаптер DP USB3.1 Gen2 UPD2018 QULE",
            "del": ["4 897 ₽"],
            "wallet": [],
        },
        {
            "nm": "1119419020",
            "lines": [
                "−45%",
                "РАСПРОДАЖА",
                "4 961 ₽",
                "9 338 ₽",
                "с WB Кошельком",
                "JPHZNB",
                "/",
                "Платы расширения UPD2018 DP + USB3.1",
                "11 октября",
            ],
            "label": "Платы расширения UPD2018 DP + USB3.1 JPHZNB",
            "del": ["9 338 ₽"],
            "wallet": [],
        },
        {
            # flattened variant: everything on one line, no DOM hints
            "nm": "1552408950",
            "lines": [
                "−7% 5 155 ₽ 5 684 ₽ с WB Кошельком Нет бренда / Карта расширения для Dell Sunic upd2018 TX5M0 11 октября"
            ],
            "label": "Карта расширения для Dell Sunic upd2018 TX5M0",
            "del": [],
            "wallet": [],
        },
        {
            # no Wallet label: the lower figure is the regular price
            "nm": "1000000001",
            "lines": ["1 200 ₽", "1 500 ₽", "Бренд", "/", "Товар", "от 100 ₽/мес"],
            "label": "",
            "del": ["1 500 ₽"],
            "wallet": [],
        },
        {"nm": "not-a-number", "lines": ["1 ₽"]},
    ],
}

CARD_PAYLOAD = {
    # verbatim from wb_dom_diag.py, 2026-09-30: WB product pages render no <h1>
    "title": "Платы расширения UPD2018 DP + USB3.1 TX5M0 JPHZNB 1345073040",
    "url": "https://www.wildberries.ru/catalog/1345073040/detail.aspx",
    "h1": "",
    "lines": [
        "JPHZNB / Платы расширения JPHZNB UPD2018 DP + USB3.1 TX5M0",
        "Нет оценок",
        "4 961 ₽",
        "5 063 ₽",
        "9 338 ₽",
        "Купить",
        "В корзину",
        "Главная",
        "Электроника",
        "Комплектующие для ПК",
        "Материнские платы",
        "JPHZNB",
        "РАСПРОДАЖА",
        "Похожие",
        "JPHZNB",
        "Платы расширения JPHZNB UPD2018 DP + USB3.1 TX5M0",
        "Нет оценок",
        "Артикул",
        "1345073040",
        "Свойство 1",
        "Цвет: Full height version",
        "ИНН",
        "0000000000",
        "Наименование продавца",
        "Jiyuan Qiyun Network Technology Co., Ltd.",
        "Адрес продавца",
        "CN, Huling Science and Technology Building, West Section of Huanghe Avenue, Other Districts, Jiyuan City, Henan Province, 410881999",
        "Номер регистрации",
        "91419001MA40X2YF91",
        "Длина упаковки",
        "22 см",
        "Характеристики и описание",
        "Возврат через заявку",
        "Материнские Платы",
        "JPHZNB",
        "В каталог бренда",
        "Материнские Платы",
        "Все товары категории",
        "4 961 ₽",
        "5 063 ₽",
        "9 338 ₽",
        "Розыгрыш",
        "Купить сейчас",
        "Добавить в корзину",
        "11 октября,",
        "склад продавца",
        "Находки из Китая",
        "5,0",
        "Оценки0",
        "Отзывов пока нет — ваш может стать первым",
        "Поделитесь мнением о покупке и помогите другим покупателям сделать выбор",
        "Смотрите также",
        "−6%",
        "5 878 ₽",
        "6 415 ₽",
        "с WB Кошельком",
        "MXRSDF",
        "/",
        "Расширительная карта AOC-SLG3-2E4R NVME",
        "11 октября",
    ],
    "wallet": [],
    "del": [],
    "seller": ["Находки из Китая 5,0"] * 7 + ["Находки из Китая"],
}


SAMSUNG_CARD_PAYLOAD = {
    # verbatim from wb_card_dump.py (nm 164379765, 2026-09-30): Russian seller, 222 ratings, no Wallet price
    "title": 'SSD накопитель 2.5" 870 EVO MZ-77E500BW 500GB Samsung 164379765 купить за 20\u00a0825\u00a0₽ в интернет\u2011магазине Wildberries',
    "h1": "",
    "lines": [
        'Samsung / SSD накопитель 2.5" 870 EVO MZ-77E500BW 500GB',
        "5",
        "·",
        "222 оценки",
        '2,5" · 500 ГБ',
        "20 825 ₽",
        "29 249 ₽",
        "Купить",
        "В корзину",
        "Главная",
        "Электроника",
        "Комплектующие для ПК",
        "Твердотельные накопители SSD",
        "Samsung",
        "Похожие",
        "Samsung",
        "Оригинал",
        'SSD накопитель 2.5" 870 EVO MZ-77E500BW 500GB',
        "5 · 222 оценки",
        "42 вопроса",
        '2,5" · 500 ГБ',
        "Артикул",
        "164379765",
        "Гарантийный срок",
        "5 лет",
        "Форм-фактор накопителя",
        '2,5"',
        "Объем накопителя",
        "500 ГБ",
        "Интерфейс",
        "SATA",
        "Тип памяти накопителя",
        "3D NAND TLC (Samsung)",
        "Максимальная скорость записи",
        "530 Мб/с",
        "Характеристики и описание",
        "Возврат через заявку",
        "Внутренние Ssd-Накопители",
        "SAMSUNG",
        "В каталог бренда",
        "Внутренние Ssd-Накопители",
        "Все товары категории",
        "20 825 ₽",
        "29 249 ₽",
        "Хорошая цена",
        "Купить сейчас",
        "Добавить в корзину",
        "4 октября,",
        "склад продавца",
        "Modern Device",
        "4,9",
        "Все 27 предложений от 7 369 ₽",
        "Все",
        "7 369 ₽",
        "Нет оценок",
        "11 октября",
        "UJII",
        "7 623 ₽",
        "Нет оценок",
        "11 октября",
        "FGGG",
        "11 964 ₽",
        "Нет оценок",
        "11 октября",
        "IT Склад",
        "Оценки222",
        "Вопросы42",
        "5,0",
        "Выбор покупателей",
        "222 оценки",
    ],
    "wallet": [],
    "del": ["16 346 ₽", "19 048 ₽", "25 670 ₽", "28 814 ₽", "14 234 ₽", "34 760 ₽", "25 600 ₽", "68 020 ₽"],
    "seller": ["Modern Device 4,9"] * 7 + ["Modern Device"],
}


# --------------------------------------------------------------- price logic


@pytest.mark.parametrize(
    ("prices", "kwargs", "expected"),
    [
        ([4961, 5063, 9338], {}, (5063, 4961, 9338)),  # product page: wallet < regular < struck
        ([4961, 9338], {"wallet_label": True}, (None, 4961, 9338)),  # search tile
        ([1000, 1500], {}, (1000, None, 1500)),  # no wallet discount
        ([1000], {}, (1000, None, None)),
        ([], {}, (None, None, None)),
        ([4961, 5063, 9338], {"wallet_hint": 4961.0}, (5063, 4961, 9338)),
        ([4961, 9338], {"wallet_hint": 4961.0}, (None, 4961, 9338)),  # 9338/4961 > 1.15 → struck
        ([4961, 5063], {"wallet_hint": 4961.0}, (5063, 4961, None)),  # small gap → regular
        ([1200, 1500], {"crossed_hint": 1500.0}, (1200, None, 1500)),
        # acceptance 2026-09-30: <del> hint present AND the Wallet label
        ([4486, 4897], {"crossed_hint": 4897.0, "wallet_label": True}, (None, 4486, 4897)),
        # acceptance 2026-09-30: product page with a <del> hint
        ([4961, 5063, 9338], {"crossed_hint": 9338.0}, (5063, 4961, 9338)),
    ],
)
def test_assign_prices(prices: list[float], kwargs: dict[str, Any], expected: tuple) -> None:
    assert D.assign_prices([float(p) for p in prices], **kwargs) == expected


def test_prices_in_skips_instalments_and_reads_nbsp() -> None:
    assert D.prices_in("от 1 234 ₽/мес") == []
    assert D.prices_in("4\u00a0961\u00a0₽ 5\u2009063 ₽") == [4961.0, 5063.0]
    assert D.prices_in("−45% РАСПРОДАЖА") == []


# --------------------------------------------------------------- search grid


def test_search_tiles_parse_and_flag_wallet_prices() -> None:
    items, warnings = D.parse_search_page(SEARCH_PAYLOAD)
    by_nm = {item["nm_id"]: item for item in items}
    assert set(by_nm) == {1517577386, 1119419020, 1552408950, 1000000001}

    qule = by_nm[1517577386]
    assert (qule["brand"], qule["name"]) == ("QULE", "Адаптер DP USB3.1 Gen2 UPD2018")
    assert (qule["price_rub"], qule["wallet_price_rub"], qule["price_original_rub"]) == (4486.0, 4486.0, 4897.0)
    assert qule["price_kind"] == "wallet"
    assert (qule["review_rating"], qule["feedbacks"]) == (5.0, 1)
    assert qule["delivery"] == "11 октября"

    ours = by_nm[1119419020]
    assert (ours["brand"], ours["name"]) == ("JPHZNB", "Платы расширения UPD2018 DP + USB3.1")
    assert (ours["price_rub"], ours["price_kind"], ours["price_original_rub"]) == (4961.0, "wallet", 9338.0)

    flat = by_nm[1552408950]
    assert flat["brand"] == ""  # «Нет бренда»
    assert (flat["price_rub"], flat["price_original_rub"]) == (5155.0, 5684.0)
    assert flat["price_kind"] == "wallet"

    hinted = by_nm[1000000001]
    assert (hinted["price_rub"], hinted["price_original_rub"], hinted["price_kind"]) == (1200.0, 1500.0, "regular")
    assert (hinted["brand"], hinted["name"]) == ("Бренд", "Товар")

    assert any("Wallet price" in w for w in warnings)


# --------------------------------------------------------------- product page


def test_card_page_reference_nm() -> None:
    item, warnings = D.parse_card_page(CARD_PAYLOAD, 1345073040)
    assert warnings == []
    assert item is not None
    assert item["name"] == "Платы расширения JPHZNB UPD2018 DP + USB3.1 TX5M0"
    assert item["brand"] == "JPHZNB"
    assert (item["price_rub"], item["wallet_price_rub"], item["price_original_rub"]) == (5063.0, 4961.0, 9338.0)
    assert item["price_kind"] == "regular"
    assert item["in_stock"] is True
    assert (item["delivery"], item["warehouse"]) == ("11 октября", "склад продавца")
    assert (item["supplier"], item["supplier_rating"]) == ("Находки из Китая", 5.0)
    assert (item["review_rating"], item["feedbacks"]) == (None, 0)
    assert item["returns"] == "Возврат через заявку"
    assert item["seller_legal_name"] == "Jiyuan Qiyun Network Technology Co., Ltd."
    assert item["seller_country"] == "CN"
    assert item["seller_registration"] == "91419001MA40X2YF91"
    assert item["seller_inn"] is None  # 0000000000 is a placeholder
    assert item["cross_border"] is True


def test_card_page_with_del_hint_keeps_wallet_and_regular_apart() -> None:
    item, _ = D.parse_card_page({**CARD_PAYLOAD, "del": ["9 338 ₽", "6 415 ₽"]}, 1345073040)
    assert item is not None
    assert (item["price_rub"], item["wallet_price_rub"], item["price_original_rub"]) == (5063.0, 4961.0, 9338.0)


def test_card_page_ignores_neighbour_hints_seen_live() -> None:
    """Acceptance 2026-09-30, second run: first <del> was the carousel's 6 415 ₽ and the
    first [class*=seller] text was «Смотрите также»."""
    payload = {**CARD_PAYLOAD, "del": ["6 415 ₽", "9 338 ₽"], "seller": ["Смотрите также", "Находки из Китая 5,0"]}
    item, _ = D.parse_card_page(payload, 1345073040)
    assert item is not None
    assert (item["price_rub"], item["wallet_price_rub"], item["price_original_rub"]) == (5063.0, 4961.0, 9338.0)
    assert (item["supplier"], item["supplier_rating"]) == ("Находки из Китая", 5.0)


def test_store_fallback_skips_section_headings() -> None:
    assert D._store_from_seller_texts(["Смотрите также", "Магазин Ромашка 4,7"]) == ("Магазин Ромашка", 4.7)
    assert D._store_from_seller_texts(["Смотрите также"]) == ("", None)


def test_card_page_name_from_title_when_no_brand_line() -> None:
    lines = [line for line in CARD_PAYLOAD["lines"] if " / " not in line]
    item, _ = D.parse_card_page({**CARD_PAYLOAD, "lines": lines}, 1345073040)
    assert item is not None
    assert item["name"] == "Платы расширения UPD2018 DP + USB3.1 TX5M0 JPHZNB"


def test_unusable_render_is_not_cached() -> None:
    assert D._usable(CARD_PAYLOAD, "card") is True
    assert D._usable({"lines": ["Главная"]}, "card") is False
    assert D._usable({"tiles": []}, "search") is False


def test_card_page_store_fallback_without_seller_hint() -> None:
    payload = {**CARD_PAYLOAD, "seller": []}
    item, _ = D.parse_card_page(payload, 1345073040)
    assert item is not None
    assert (item["supplier"], item["supplier_rating"]) == ("Находки из Китая", 5.0)


def test_card_page_other_nm_is_skipped() -> None:
    item, warnings = D.parse_card_page(CARD_PAYLOAD, 1111111111)
    assert item is None
    assert "page shows 1345073040" in warnings[0]


def test_card_page_empty_render() -> None:
    item, warnings = D.parse_card_page({"h1": "", "title": "Интернет‑магазин Wildberries", "lines": []}, 42)
    assert item is None and "rendered no product" in warnings[0]


def test_card_page_russian_seller_is_domestic() -> None:
    lines = [
        "Бренд / Товар",
        "4,8 · 1 234 оценки",
        "1 000 ₽",
        "Добавить в корзину",
        "завтра",
        "Магазин 4,9",
        "Артикул",
        "42",
        "Адрес продавца",
        "Россия, Москва",
        "ИНН",
        "7700000001",
    ]
    item, _ = D.parse_card_page({"h1": "Товар", "lines": lines, "seller": []}, 42)
    assert item is not None
    assert item["cross_border"] is False and item["seller_country"] == "RU"
    assert (item["review_rating"], item["feedbacks"]) == (4.8, 1234)
    assert item["seller_inn"] == "7700000001"
    assert item["delivery"] == "завтра"


# --------------------------------------------------------------- render contract


class _FakePage:
    def __init__(self, probes: list[dict[str, Any]], extract: dict[str, Any]) -> None:
        self._probes = probes
        self._extract = extract
        self.url = "https://www.wildberries.ru/"

    async def evaluate(self, expression: str, arg: object = None) -> Any:
        if expression is D.PROBE_JS:
            probe = self._probes.pop(0) if len(self._probes) > 1 else self._probes[0]
            return json.dumps(probe)
        return json.dumps(self._extract)


def _patch_open_page(monkeypatch: pytest.MonkeyPatch, page: _FakePage) -> list[str]:
    import mcp_core.transport.chrome_cdp as cdp

    opened: list[str] = []

    @asynccontextmanager
    async def fake_open_page(url: str, wait_ms: int = 0, *, allowed_hosts: Any = None):
        opened.append(url)
        assert allowed_hosts == D.ALLOWED_HOSTS
        yield page

    monkeypatch.setattr(cdp, "open_page", fake_open_page)
    monkeypatch.setattr(D._settings, "dom_min_gap", 0.0)
    monkeypatch.setattr(D._settings, "dom_wait_s", 2.0)
    D._dom_cache.clear()
    return opened


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_render_waits_out_the_browser_check(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage(
        [{"state": "challenge"}, {"state": "ok", "tiles": 3}, {"state": "ok", "tiles": 3}],
        SEARCH_PAYLOAD,
    )
    opened = _patch_open_page(monkeypatch, page)
    data = _run(D.render(D.search_url("UPD2018"), D.SEARCH_EXTRACT_JS, "search"))
    assert data["tiles"] and opened == ["https://www.wildberries.ru/catalog/0/search.aspx?search=UPD2018"]
    # cached: a second call does not navigate again
    _run(D.render(D.search_url("UPD2018"), D.SEARCH_EXTRACT_JS, "search"))
    assert len(opened) == 1


def test_card_render_waits_for_the_store_block(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage(
        [
            {"state": "ok", "sku": True, "rub": True, "store": False},
            {"state": "ok", "sku": True, "rub": True, "store": False},
            {"state": "ok", "sku": True, "rub": True, "store": True},
        ],
        CARD_PAYLOAD,
    )
    _patch_open_page(monkeypatch, page)
    monkeypatch.setattr(D._settings, "dom_store_wait_s", 10.0)
    _run(D.render(D.card_url(1345073040), D.CARD_EXTRACT_JS, "card"))
    assert page._probes == [{"state": "ok", "sku": True, "rub": True, "store": True}]  # polled until the store showed


def test_card_render_store_wait_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage([{"state": "ok", "sku": True, "rub": True, "store": False}], CARD_PAYLOAD)
    _patch_open_page(monkeypatch, page)
    monkeypatch.setattr(D._settings, "dom_store_wait_s", 0.0)
    data = _run(D.render(D.card_url(1345073041), D.CARD_EXTRACT_JS, "card"))
    assert data["lines"]  # returned without the store, no error


def test_card_render_waits_briefly_for_other_offers(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage(
        [
            {"state": "ok", "sku": True, "rub": True, "store": True, "offers": False},
            {"state": "ok", "sku": True, "rub": True, "store": True, "offers": True},
        ],
        SAMSUNG_CARD_PAYLOAD,
    )
    _patch_open_page(monkeypatch, page)
    monkeypatch.setattr(D._settings, "dom_offers_wait_s", 10.0)
    _run(D.render(D.card_url(164379765), D.CARD_EXTRACT_JS, "card"))
    assert page._probes == [{"state": "ok", "sku": True, "rub": True, "store": True, "offers": True}]


def test_card_render_offers_wait_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage([{"state": "ok", "sku": True, "rub": True, "store": True, "offers": False}], CARD_PAYLOAD)
    _patch_open_page(monkeypatch, page)
    monkeypatch.setattr(D._settings, "dom_offers_wait_s", 0.0)
    data = _run(D.render(D.card_url(1345073042), D.CARD_EXTRACT_JS, "card"))
    assert data["lines"]


def test_render_stops_on_suspicious_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage([{"state": "blocked", "captcha": False}], {})
    opened = _patch_open_page(monkeypatch, page)
    with pytest.raises(ToolError) as exc:
        _run(D.render(D.card_url(1), D.CARD_EXTRACT_JS, "card"))
    body = json.loads(str(exc.value))
    assert body["error"] == "transport_down" and "Подозрительная активность" in body["message"]
    assert len(opened) == 1  # no retry


def test_render_captcha_requires_the_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage([{"state": "blocked", "captcha": True}], {})
    _patch_open_page(monkeypatch, page)
    with pytest.raises(ToolError) as exc:
        _run(D.render(D.card_url(2), D.CARD_EXTRACT_JS, "card"))
    body = json.loads(str(exc.value))
    assert body["error"] == "challenge_required" and body["requires_user_action"] is True


def test_render_challenge_that_never_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage([{"state": "challenge"}], {})
    _patch_open_page(monkeypatch, page)
    monkeypatch.setattr(D._settings, "dom_wait_s", 0.5)
    with pytest.raises(ToolError) as exc:
        _run(D.render(D.card_url(3), D.CARD_EXTRACT_JS, "card"))
    assert "did not clear" in json.loads(str(exc.value))["message"]


# --------------------------------------------------------------- tool wiring


def test_tools_route_to_dom_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server._settings, "transport", "dom")

    async def fake_render(url: str, js: str, want: str) -> dict[str, Any]:
        return SEARCH_PAYLOAD if want == "search" else CARD_PAYLOAD

    monkeypatch.setattr(D, "render", fake_render)

    search = _run(server.wb_search(query="UPD2018"))
    assert search.count == 4 and all(i.transport == "dom" for i in search.items)
    assert all(i.brand for i in search.items if i.nm_id in (1517577386, 1119419020))
    assert any("Wallet price" in w for w in search.meta.warnings)

    card = _run(server.wb_card(nm_ids=[1345073040]))
    assert card.count == 1 and card.items[0].transport == "dom"
    only = card.items[0]
    assert (only.price_rub, only.wallet_price_rub, only.price_kind) == (5063.0, 4961.0, "regular")
    assert any("cross-border" in w for w in card.meta.warnings)


def test_card_dom_caps_navigations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server._settings, "transport", "dom")
    monkeypatch.setattr(server._settings, "dom_max_cards", 2)
    seen: list[str] = []

    async def fake_render(url: str, js: str, want: str) -> dict[str, Any]:
        seen.append(url)
        return {"h1": "", "lines": []}

    monkeypatch.setattr(D, "render", fake_render)
    card = _run(server.wb_card(nm_ids=[1, 2, 3]))
    assert len(seen) == 2 and card.count == 0
    assert any("read the first 2" in w for w in card.meta.warnings)


def test_api_transport_is_the_default() -> None:
    assert type(server._settings).model_fields["transport"].default == "api"


def test_card_page_russian_seller_with_ratings_seen_live() -> None:
    item, warnings = D.parse_card_page(SAMSUNG_CARD_PAYLOAD, 164379765)
    assert item is not None
    assert (item["brand"], item["name"]) == ("Samsung", 'SSD накопитель 2.5" 870 EVO MZ-77E500BW 500GB')
    assert (item["review_rating"], item["feedbacks"]) == (5.0, 222)  # was (2.0, 22): «222 оценки» read as «2» + «22»
    assert (item["price_rub"], item["wallet_price_rub"], item["price_original_rub"]) == (20825.0, None, 29249.0)
    assert (item["supplier"], item["supplier_rating"]) == ("Modern Device", 4.9)
    assert (item["delivery"], item["warehouse"]) == ("4 октября", "склад продавца")
    assert item["warranty"] == "5 лет"
    assert item["original_badge"] is True
    assert (item["other_offers_count"], item["other_offers_from_rub"]) == (27, 7369.0)
    assert item["seller_legal_name"] is None and item["cross_border"] is None
    assert any("anomalously cheap" in w and "-65%" in w for w in warnings)


def test_rating_count_line_alone_is_not_a_rating() -> None:
    assert D.parse_rating(["222 оценки"]) == (None, None)
    assert D.parse_rating(["5", "·", "222 оценки"]) == (5.0, 222)
    assert D.parse_rating(["4,8 1 234 оценки"]) == (4.8, 1234)
    assert D.parse_rating(["5 · 1 оценка"]) == (5.0, 1)


def test_reference_card_has_no_offer_anomaly_and_no_badge() -> None:
    item, warnings = D.parse_card_page(CARD_PAYLOAD, 1345073040)
    assert item is not None
    assert item["original_badge"] is None and item["other_offers_count"] is None
    assert not any("anomalously" in w for w in warnings)


def test_reviews_score_h1_is_not_the_product_name() -> None:
    """Live 2026-09-30 after 0012: the longer wait let the reviews widget render, whose
    «5,0» score is the only <h1> on the page; it came back as the product name."""
    item, _ = D.parse_card_page({**SAMSUNG_CARD_PAYLOAD, "h1": "5,0"}, 164379765)
    assert item is not None
    assert item["name"] == 'SSD накопитель 2.5" 870 EVO MZ-77E500BW 500GB'
    lines = [line for line in SAMSUNG_CARD_PAYLOAD["lines"] if " / " not in line]
    item, _ = D.parse_card_page({**SAMSUNG_CARD_PAYLOAD, "lines": lines, "h1": "Название товара"}, 164379765)
    assert item is not None and item["name"] == "Название товара"
