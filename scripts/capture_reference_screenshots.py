"""Capture reference screenshots used by the UI moodboard."""

from pathlib import Path
from playwright.sync_api import sync_playwright


SHOTS = [
    ("dribbble_dashboard_ui.png", "https://dribbble.com/tags/dashboard-ui"),
    ("dribbble_performance_dashboard.png", "https://dribbble.com/search/performance%20dashboard"),
    ("awwwards_dashboard_gallery.png", "https://www.awwwards.com/websites/dashboard/"),
    ("powerbi_design_tips.png", "https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards-design-tips"),
    ("tableau_dashboard_best_practices.png", "https://www.tableau.com/blog/best-practices-for-building-effective-dashboards"),
    ("metabase_filters.png", "https://www.metabase.com/docs/latest/dashboards/filters"),
    ("datadog_dashboards_product.png", "https://www.datadoghq.com/product/platform/dashboards/"),
    ("looker_dashboards_docs.png", "https://cloud.google.com/looker/docs/viewing-dashboards"),
    ("cultureamp_action_dashboard.png", "https://support.cultureamp.com/en/articles/7048527-admin-s-action-dashboard"),
    ("lattice_manager_reporting.png", "https://help.lattice.com/hc/en-us/articles/1500004773502-The-Reporting-Page-for-Managers"),
]


def main() -> None:
    out = Path("docs/design/moodboard/screenshots")
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1512, "height": 982})

        for filename, url in SHOTS:
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3500)
                page.screenshot(path=str(out / filename), full_page=True)
                print(f"OK {filename}")
            except Exception as exc:  # pragma: no cover
                print(f"FAIL {filename}: {exc}")
            finally:
                page.close()

        browser.close()


if __name__ == "__main__":
    main()
