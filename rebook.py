import tempfile
import dateparser
import datetime
import telegram_send
from calendar import monthrange
from playwright.sync_api import sync_playwright,
     Page as PlaywrightPage, TimeoutError as PlaywrightTimeoutError
from pydantic import BaseSettings, SecretStr


class Settings(BaseSettings):
    EMAIL: str
    PWD: SecretStr

    class Config:
        env_prefix = "UDI_"
        env_file = ".env"
        env_file_encoding = "utf-8"


def send_success(page: PlaywrightPage, msg: str):
    telegram_send.send(messages=[msg])
    with tempfile.TemporaryFile("r+b") as fp:
        encoded_img = page.screenshot(type="png")
        fp.write(encoded_img)
        fp.seek(0, 0)
        telegram_send.send(images=[fp])


def main():
    config = Settings()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("https://selfservice.udi.no/en-gb/")
            # click on log in button
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

            # book appointment
            page.click(book_btn_id)
        except PlaywrightTimeoutError:
            msg = "Failed to login. Check your password."
            print(msg)
            telegram_send.send(messages=[msg])
            return

        # click on the first one in the list
        page.click(
            "#ctl00_BodyRegion_PageRegion_MainRegion_ApplicationOverview_applicationOverviewListView_ctrl0_btnBookAppointment"
        )

        change_btn_id = "#ctl00_PageRegion_MainContentRegion_ViewControl_spnReceiptAndBooking_BookingSummaryInfo_btnChangeBooking"
        try:
            page.wait_for_selector(change_btn_id, timeout=5000)
        except PlaywrightTimeoutError:
            print("No appointments to rebook.")
            return

        current_booking_id = "#ctl00_PageRegion_MainContentRegion_ViewControl_spnReceiptAndBooking_BookingSummaryInfo_lblDate"
        current_booking = page.text_content(current_booking_id)
        current_booking = dateparser.parse(current_booking)
        current_booking_date = datetime.date(current_booking.year, current_booking.month, current_booking.day)

        with page.expect_navigation():
            page.click(change_btn_id)

        # button to go to the next month
        next_btn_id = "#ctl00_BodyRegion_PageRegion_MainRegion_appointmentReservation_appointmentCalendar_btnNext"

        # initialize view_month to be just slightly less than the current booking
        view_month = current_booking - (current_booking - dateparser.parse("1 day"))
        # iterate over months trying to find available appointments
        rebooking_possible = False
        while current_booking > view_month:
            view_month_txt = page.query_selector("h2").inner_text()
            view_month = dateparser.parse(view_month_txt)

            num_closed = len(page.query_selector_all('css=[class="bookingCalendarClosedDay"]'))
            num_days_in_month = monthrange(view_month.year, view_month.month)[1]
            if num_days_in_month == num_closed:
                print("Reached a fully closed month.")
                break

            bookable = []
            for class_id in [".bookingCalendarHalfBookedDay", ".bookingCalendarBookableDay", ".bookingCalendarBookedDay"]:
                bookable.extend(page.query_selector_all(class_id))

            if bookable:
                bookable = sorted(bookable, key=lambda x: int(x.inner_text().split()[0]))
                bookable_day = int(bookable[0].inner_text().split()[0])
                bookable_date = datetime.date(view_month.year, view_month.month, bookable_day)
                if bookable_date < current_booking_date:
                    msg = f"It is possible to rebook the appointment on {bookable_day}, {view_month_txt}!"
                    send_success(page, msg)
                    print(msg) # Also print message to stdout/log
                    rebooking_possible = True
                    break

            with page.expect_navigation():
                page.click(next_btn_id)
            print(f"No possibilities to rebook for month {view_month_txt}.")

        if not rebooking_possible:
            print(f"No possibilities to rebook date earlier than {current_booking_date}.")



if __name__ == "__main__":
    main()
