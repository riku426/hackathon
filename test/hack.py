import requests

URL = 'https://0kqan9y2mg9d.cybozu.com/k/v1/record.json?app=1&id=1'

API_TOKEN = "lnl2Tbtwiy2i8QR4kMGMgCd4llv3thiccjpvcda6	"

def get_kintone(url, api_token):
    """kintoneのレコードを1件取得する関数"""
    headers = {"X-Cybozu-API-Token": api_token}
    resp = requests.get(url, headers=headers)

    return resp

if __name__ == "__main__":
    RESP = get_kintone(URL, API_TOKEN)

    print(RESP.text)