"""The figures section of the report in a real browser: rows line up, text stays readable, narrow screens scroll the figure instead of
shrinking it. The report here is built from real plots of a three-sample job."""
import pytest

pytest.importorskip("selenium", reason="selenium is not installed")

from .test_results_browser import CDN, STUB_3DMOL, open_page, parts  # noqa: F401  (parts is a fixture)

ROWS_JS = """
const box = e => { const r = e.getBoundingClientRect(); return {top: Math.round(r.top * 10) / 10, height: Math.round(r.height * 10) / 10, width: Math.round(r.width * 10) / 10, left: r.left, right: r.right}; };
return [...document.querySelectorAll('.bz-figrow')].map(row => ({
  kind: row.className.replace('bz-figrow ', ''),
  figs: [...row.querySelectorAll('.bz-fig')].map(f => {
    const img = f.querySelector('img'), r = box(f), im = box(img);
    return {card: r, img: im, scale: img.clientWidth / img.naturalWidth, inside: im.left >= r.left - 0.5 && im.right <= r.right + 0.5,
            clipsX: f.querySelector('.bz-fig-img').scrollWidth - f.querySelector('.bz-fig-img').clientWidth};
  })}));
"""


def rows(driver):
    return driver.execute_script(ROWS_JS)


def load(driver, parts, width, name):                        # noqa: F811
    open_page(driver, parts, parts["report"].replace(CDN, STUB_3DMOL), name, width)
    return rows(driver)


@pytest.mark.parametrize("width", [1100, 1280])
def test_cards_in_a_row_start_together_and_are_equally_tall(driver, parts, width):   # noqa: F811
    rs = load(driver, parts, width, f"layout-{width}")
    assert [r["kind"] for r in rs] == ["bz-figrow--pae"] * 3 + ["bz-figrow--even"], [r["kind"] for r in rs]
    for r in rs:
        a, b = (f["card"] for f in r["figs"])
        assert abs(a["top"] - b["top"]) <= 1, f"{r['kind']}: cards start at different heights ({a['top']} vs {b['top']})"
        assert abs(a["height"] - b["height"]) <= 3, f"{r['kind']}: cards differ in height ({a['height']} vs {b['height']}px): ragged row"
        assert all(f["inside"] for f in r["figs"])
    pae, plddt = (f["img"] for f in rs[0]["figs"])
    assert abs(pae["height"] - plddt["height"]) <= 4, f"PAE {pae['height']}px vs pLDDT {plddt['height']}px"


@pytest.mark.parametrize("width", [1100, 1280])
def test_figure_text_is_not_shrunk_to_unreadable_size(driver, parts, width):   # noqa: F811
    """The plots are drawn with 9.5-12.5 pt text at 150 dpi; shown at about half of that size or more it stays readable."""
    for r in load(driver, parts, width, f"scale-{width}"):
        for f in r["figs"]:
            assert f["scale"] >= 0.5, f"{r['kind']}: figure shown at {f['scale']:.2f} of its size"


@pytest.mark.parametrize("width", [620, 768, 900])
def test_narrow_pages_stack_the_figures_full_width(driver, parts, width):   # noqa: F811
    rs = load(driver, parts, width, f"stack-{width}")
    for r in rs:
        tops = [f["card"]["top"] for f in r["figs"]]
        assert tops == sorted(tops) and (len(tops) == 1 or tops[1] > tops[0] + 100), f"{r['kind']} did not stack"
        widths = {round(f["card"]["width"]) for f in r["figs"]}
        assert len(widths) == 1, f"stacked cards differ in width: {widths}"
        assert all(f["scale"] <= 1.001 for f in r["figs"]), f"{r['kind']}: a stacked figure was enlarged past its pixel width"


@pytest.mark.parametrize("width", [360, 414])
def test_on_a_phone_a_figure_scrolls_inside_its_card_instead_of_shrinking(driver, parts, width):   # noqa: F811
    rs = load(driver, parts, width, f"phone-{width}")
    for r in rs:
        for f in r["figs"]:
            assert f["img"]["width"] >= 430, f"{r['kind']}: figure squeezed to {f['img']['width']}px"
            assert f["clipsX"] > 0, "a figure wider than the card must be scrollable"
    doc = driver.execute_script("return document.documentElement.scrollWidth - window.innerWidth")
    assert doc <= 1, f"the page itself scrolls sideways by {doc}px"
