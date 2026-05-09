from news_crawlers.changzhi_gjj import crawl_changzhi_gjj_zxwj
import json


if __name__ == '__main__':
    items = crawl_changzhi_gjj_zxwj()
    out = []
    for i in items:
        out.append({
            'title': i.get('title'),
            'url': i.get('url'),
            'date': str(i.get('date')) if i.get('date') else None,
        })
    print(json.dumps(out, ensure_ascii=False, indent=2))
