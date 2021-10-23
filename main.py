import tempfile
import telegram_send
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from pydantic import BaseSettings, SecretStr


class Settings(BaseSettings):
    EMAIL: str
    PWD: SecretStr

    class Config:
        env_prefix = "UDI_"
        env_file = ".env"
        env_file_encoding = "utf-8"


def main():
    config = Settings()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto("https://selfservice.udi.no/en-gb/")
            page.click("#ctl00_BodyRegion_PageRegion_MainRegion_LogInHeading")

            page.type("input[type=email]", config.EMAIL)
            page.type("input[type=password]", config.PWD.get_secret_value())
            page.click("#next")
        except PlaywrightTimeoutError:
            msg = "Seems like UDI website is down or you are offline"
            print(msg)
            telegram_send.send(messages=[msg])
            return

        try:
            book_btn_id: str = "#ctl00_BodyRegion_PageRegion_MainRegion_IconNavigationTile2_heading"
            page.wait_for_selector(book_btn_id)
            page.click(book_btn_id)
        except playwright.helper.TimeoutError:
            msg = "Failed to login. Check your password."
            print(msg)
            telegram_send.send(messages=[msg])
            return

        # click on the first one in the list
        page.click(
            "#ctl00_BodyRegion_PageRegion_MainRegion_ApplicationOverview_applicationOverviewListView_ctrl0_btnBookAppointment"
        )

        try:
            page.wait_for_selector(
                "#ctl00_PageRegion_MainContentRegion_ViewControl_spnReceiptAndBooking_divErrorMessageForNoAvailabelAppointments",
                timeout=5000,
            )
            print("No appointments")
            return
        except PlaywrightTimeoutError:
            msg = "Looks like UDI is ready for appointments"
            telegram_send.send(messages=[msg])

            with tempfile.TemporaryFile("r+b") as fp:
                encoded_img = page.screenshot(type="png")
                fp.write(encoded_img)
                fp.seek(0, 0)
                telegram_send.send(images=[fp])


if __name__ == "__main__":
    main()
