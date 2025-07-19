import re
from datetime import timezone, timedelta

# Константы
URL_PATTERN = re.compile(
    r'^(https?://)?'
    r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
    r'(:\d+)?'
    r'(/[\w\-._~:/?#[\]@!$&\'()*+,;=]*)?$'
)
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png']

MOSCOW_TZ = timezone(timedelta(hours=3))
TIME_PATTERN = re.compile(r'^\s*(\d{1,2}):(\d{2})\s*$')
