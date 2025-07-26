from data.config import config_settings

base_url = config_settings.base_url

url_users = f"{base_url}/users/"
url_mailing = f"{base_url}/mailings/"
url_loyalty = f"{base_url}/loyalty-cards/"
url_subscription = f"{base_url}/subscriptions/"
url_resident = f"{base_url}/residents/"
url_category = f"{base_url}/categories/"
url_point_transactions_accrue = f'{base_url}/resident/points-transactions/accrue/'
url_point_transactions_deduct = f"{base_url}/resident/points-transactions/deduct/"
url_event = f"{base_url}/events/"
url_promotions = f"{base_url}/promotions/"
url_verify_pin = f"{base_url}/verify-pin/"

