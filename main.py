import tempfile

import playwright.helper
import telegram_send
from playwright import sync_playwright
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
        page = browser.newPage()
        page.goto("https://selfservice.udi.no/")
        page.click("#ctl00_BodyRegion_PageRegion_MainRegion_LogInHeading")

        page.type("input[type=email]", config.EMAIL)
        page.type("input[type=password]", config.PWD.get_secret_value())
        page.click("#next")

        try:
            # book appointment
            page.click("#ctl00_BodyRegion_PageRegion_MainRegion_IconNavigationTile2_heading")
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
            page.waitForSelector(
                "#ctl00_PageRegion_MainContentRegion_ViewControl_spnReceiptAndBooking_divErrorMessageForNoAvailabelAppointments",
                timeout=5000,
            )
            # No appointments
            print("No appointments")
            return
        except playwright.helper.TimeoutError:
            msg = "Looks like UDI is ready for appointments"
            telegram_send.send(messages=[msg])

            with tempfile.TemporaryFile("r+b") as fp:
                encoded_img = page.screenshot(type="png")
                fp.write(encoded_img)
                fp.seek(0, 0)
                telegram_send.send(images=[fp])


if __name__ == "__main__":
    main()
