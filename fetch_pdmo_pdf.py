import requests
URL = "https://www.treasury.gov.lk/api/file/c5ac95c5-8753-45f9-808f-ee4fa5e71654"
resp = requests.get(URL, verify=False)
print(resp.headers)
print(resp.content[:200])
