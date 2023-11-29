import requests
import openpyxl


from bs4 import BeautifulSoup

url = 'https://www.yinfans.me'
hd = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188'
}

#
def getmanget(hsoup):
    ret = hsoup.find_all('a')
    for n in ret:
        if 'magnet' in str(n) :
            return n['href']
    return None


def saveExcel( data,page):
    # 创建一个新的Excel文档
    workbook = openpyxl.Workbook()

    # 选择默认的工作表
    sheet = workbook.active
    for i in range(len(data)):
        sheet.cell(row=i+1, column=1, value=data[i])
    workbook.save('movie4k'+str(page)+'.xlsx')
    workbook.close()

for i in range(13, 50):
    url = 'https://www.yinfans.me/page/' + str(i)
    res = requests.get(url, headers=hd)
    res.encoding = 'utf8'
    soup = BeautifulSoup(res.text, 'html.parser')
    ret = soup.find_all(class_='zoom', rel='bookmark')
    info = []
    for x in ret:
        href=x["href"]
        hres = requests.get(href,headers=hd)
        hres.encoding = 'utf8'
        hsoup = BeautifulSoup(hres.text, 'html.parser')

        # pat = re.compile(r'◎译  名(.*)\n')
        # ret = re.findall(pat, str(hsoup))
        # for n in ret:
        #     n = n.replace(u'\u3000', u'')
        #     info.append(str(n).split('/')[0])
        #
        # pat = re.compile(r'◎年  代(.*)\n')
        # ret = re.findall(pat, str(hsoup))
        # for n in ret:
        #     n = n.replace(u'\u3000', u'')
        #     info.append(str(n))
        #
        # pat = re.compile(r'◎产  地(.*)\n')
        # ret = re.findall(pat, str(hsoup))
        # for n in ret:
        #     n = n.replace(u'\u3000', u'')
        #     info.append(str(n).split('/')[0])
        #
        # pat = re.compile(r'◎类  别(.*)\n')
        # ret = re.findall(pat, str(hsoup))
        # for n in ret:
        #     n = n.replace(u'\u3000', u'')
        #     info.append(str(n).split('/')[0])
        #
        # pat = re.compile(r'◎上映日期(.*)\n')
        # ret = re.findall(pat, str(hsoup))
        # for n in ret:
        #     n = n.repla
        mat = getmanget(hsoup)
        if mat:
            info.append(str(mat).split('&')[0])
    saveExcel(info,i)
