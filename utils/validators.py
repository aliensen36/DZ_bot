import re

name_pattern = re.compile(r"^[А-Яа-яA-Za-zёЁ\-]{2,}$")
email_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$")