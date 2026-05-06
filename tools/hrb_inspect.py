import requests,re
from bs4 import BeautifulSoup
url='https://www.hrbgjj.org.cn/zxwj/index.jhtml'
resp = requests.get(url, timeout=15)
resp.encoding = resp.apparent_encoding
soup = BeautifulSoup(resp.text,'lxml')
links = soup.find_all('a', href=re.compile(r'/zxwj/\d+\.jhtml$'))
print('found', len(links))
for i,a in enumerate(links[:10]):
    print('----', i)
    print('a_text:', repr(a.get_text()))
    print('href:', a.get('href'))
    parent = a.parent
    print('parent_tag:', parent.name if parent else None)
    print('parent_text_repr:', repr(parent.get_text(' ')))
    ns = a.next_sibling
    print('next_sibling_repr:', repr(ns))
    # following siblings
    el = a
    s = []
    for _ in range(3):
        el = el.next_sibling
        s.append(repr(el))
    print('next 3 siblings:', ' | '.join(s))
