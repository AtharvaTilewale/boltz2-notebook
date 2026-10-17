import os

import pytest

from .harness import Server, find_firefox


@pytest.fixture(autouse=True)
def _fresh_theme(monkeypatch):
    """The session's theme is process-wide state; every test starts from the default."""
    from boltz2nb.ui.theme import reset_theme

    monkeypatch.delenv("BOLTZ2NB_THEME", raising=False)
    reset_theme()
    yield
    reset_theme()


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    with Server(tmp_path_factory.mktemp("bz_ui_base")) as s:
        yield s


@pytest.fixture(scope="session")
def driver():
    pytest.importorskip("selenium", reason="selenium is not installed")
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    ff, gd = find_firefox()
    if not ff or not gd:
        pytest.skip("Firefox and geckodriver are needed for browser tests (set BZ_FIREFOX / BZ_GECKODRIVER)")
    opts = Options()
    opts.add_argument("-headless")
    opts.binary_location = ff
    opts.set_preference("layout.css.devPixelsPerPx", "1.0")
    drv = webdriver.Firefox(options=opts, service=Service(executable_path=gd, log_output=os.devnull))
    drv.set_page_load_timeout(60)
    yield drv
    drv.quit()
