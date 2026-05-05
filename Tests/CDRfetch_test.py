import pandas as pd
from CDR14_main import fetch_cdr

df = fetch_cdr(
    ['8801585724571'],
    '2026-01-10',
    '2026-02-01',
    '00:00',
    '23:59'
)
print(df)
