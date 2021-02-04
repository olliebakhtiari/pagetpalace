# Local.
from pagetpalace.tools import get_config_dict_from_s3


_EMAIL_CONFIG = get_config_dict_from_s3('email_config.json')
PAGETPALACELIVE = get_config_dict_from_s3('pagetpalacelive.json')
PAGETPALACEDEMO = get_config_dict_from_s3('demo.json')

EMAIL_ADDRESS = _EMAIL_CONFIG['EMAIL_ADDRESS']
EMAIL_ACCOUNT_PASSWORD = _EMAIL_CONFIG['EMAIL_ACCOUNT_PASSWORD']
EMAIL_DEFAULT_RECEIVERS = _EMAIL_CONFIG['EMAIL_DEFAULT_RECEIVERS']
