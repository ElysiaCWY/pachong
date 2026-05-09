from news_crawlers.jcgov import crawl_jcgov_policy
import json
import datetime
from news_crawlers.common import now_cn


if __name__ == '__main__':
    now = now_cn()
    items = crawl_jcgov_policy()
    filtered = []
    for i in items:
        d = i.get('date')
        if d is None:
            continue
        dt = datetime.datetime(d.year, d.month, d.day, tzinfo=now.tzinfo)
        delta = now - dt
        if 0 <= delta.total_seconds() <= 24*3600:
            filtered.append({'title': i.get('title'), 'url': i.get('url'), 'date': str(d)})

    print(json.dumps(filtered, ensure_ascii=False, indent=2))
