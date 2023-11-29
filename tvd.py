from collections import namedtuple
from datetime import datetime
import math
import asyncio
import logging

from typing import List, Tuple, Dict
from random import choice

import aiohttp
import typer
from deta import Deta
from bs4 import BeautifulSoup

app = typer.Typer()
# 复制自https://gist.github.com/pzb/b4b6f57144aea7827ae4
ua_list = [
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.94 Chrome/37.0.2062.94 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0',
]

logger = logging.getLogger("iptv-checker")
Info = namedtuple("Info", ["header", "url", "score"])

gorup_title_map = {
    'group-title="Undefined"': 'group-title="未定义"',
    'group-title="Entertainment"': 'group-title="娱乐"',
    'group-title="Movies"': 'group-title="电影"',
    'group-title="Science"': 'group-title="科技"',
    'group-title="Kids"': 'group-title="儿童"',
    'group-title="Business"': 'group-title="商业"',
    'group-title="Sports"': 'group-title="体育"',
    'group-title="Lifestyle"': 'group-title="生活时尚"',
    'group-title="Culture"': 'group-title="文化"',
    'group-title="Culture;News"': 'group-title="文化与新闻"',
    'group-title="Classic"': 'group-title="经典"',
    'group-title="Religious"': 'group-title="宗教"',
    'group-title="Documentary"': 'group-title="纪录片"',
    'group-title="News"': 'group-title="新闻"',
    'group-title="General"': 'group-title="综合"',
    'group-title="Education"': 'group-title="教育"',
    'group-title="Music"':  'group-title="音乐"'
}

score_map: Dict[str, int] = {
    "卫视": -1,
    "CCTV": -1,
    "湖南卫视": -2,
    "浙江卫视": -1,
    "江苏卫视": -1,
    "浙江卫视": -1,
}

header_tpl = '#EXTINF:-1 tvg-id="" tvg-country="CN" tvg-language="" tvg-logo="" group-title="未定义",{name}'

def ua() -> str:
    return choice(ua_list)

def score(info: Info):
    for k, v in score_map.items():
        if k in info.header:
            info = info._replace(score=info.score + v)
    return info

def filters(info) -> bool:
    return True

def replace(info: Info):
    for k, v in gorup_title_map.items():
        if k in info.header:
            header: str = info.header
            header = header.replace(k ,v)
            info = info._replace(header=header)
            break
    return info

async def test(sess: aiohttp.ClientSession, info: Info) -> bool:
    try:
        async with sess.get(info.url, headers={"User-Agent": ua()}) as resp:
            if resp.ok:
                return True
    except Exception:
        logger.debug(f"播放地址无效: {info.url}")
        return False


async def checker(urls: List[Info], timeout: int = 2) -> List[Info]:
    new_infos = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(timeout)) as sess:
        for url in urls:
            ok = await test(sess, url)
            if ok:
                new_infos.append(url)
    return new_infos


async def crawl() -> List[Info]:
    source_url = "http://m.hunanweishi.tv/"
    infos = []
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(5)) as sess:
            async with sess.get(source_url, headers={"User-Agent": ua()}) as resp:
                soup = BeautifulSoup(await resp.text(encoding="gb2312"), "lxml")
                options = soup.select("div#playbox option")
                for opt in options:
                    url = opt.attrs["value"]
                    header = header_tpl.format(name="湖南卫视")
                    infos.append(Info(header, url, -10))
                return infos
    except Exception as exc:
        logger.debug(f"请求{source_url}失败: " + str(exc))


async def run(index_timeout, index_url, timeout, workers) -> Tuple[str, List[Info]]:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(index_timeout)) as sess:
            resp = await sess.get(index_url)
            data = await resp.text()
    except Exception:
        msg = typer.style("下载播放播放源失败", fg=typer.colors.WHITE, bg=typer.colors.RED)
        typer.echo(msg, err=True)
        raise

    url_start_index = data.index("#EXTINF")
    index_header = data[:url_start_index]
    infos = []
    header = []
    url = ""
    for line in data[url_start_index:].splitlines():
        if line.startswith("#"):
            header.append(line)
        elif line.startswith("http"):
            url = line
        else:
            raise ValueError(f"未知的m3u8格式: {line}")

        if url:
            header = "\n".join(header)
            infos.append(Info(header, url, 0))
            header = []
            url = ""

    logger.debug(f"一共有{len(infos)}条播放地址")
    step = math.ceil(len(infos) / workers)
    futures = []
    # infos = infos[:10]
    for i in range(workers):
        _infos = infos[i*step:(i+1)*step]
        # 如果workers大于infos数量就会出现空列表
        if _infos:
            futures.append(asyncio.ensure_future(checker(_infos, timeout)))

    ret = await asyncio.wait(futures)
    # print(ret)
    infos: List[Info] = [i for task in ret[0] for i in task.result()]
    return index_header, infos

@app.command()
def main(
    index_timeout: int = typer.Option(30, help="访问播放源的超时时间(秒)"),
    index_url: str = typer.Option("https://iptv-org.github.io/iptv/countries/cn.m3u", help="iptv地址播放源的url"),
    timeout: int = typer.Option(2, help="每个测试url地址的超时时间(秒)"),
    workers: int = typer.Option(32, help="工作进程数"),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True)
):
    log_level = 50 - 10 * verbose
    if log_level < 0:
        log_level = 10
    logging.basicConfig(level=log_level, format="%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s")
    loop = asyncio.get_event_loop()
    start = datetime.now()
    logger.debug("开始检测")
    end = datetime.now()
    index_header, infos = loop.run_until_complete(run(index_timeout, index_url, timeout, workers))
    logger.debug(f"检测花费时间: {end - start}")

    logger.debug(f"检测之后有{len(infos)}条新播放地址")
    new_infos = []
    for info in infos:
        info = score(info)
        info = replace(info)
        if not filters(info):
            continue
        new_infos.append(info)

    new_infos.sort(key=lambda info:info.score)
    other_infos = loop.run_until_complete(crawl())
    if other_infos:
        new_infos = other_infos + new_infos

    lines = [f"{i.header}\n{i.url}" for i in new_infos]
    index_header = index_header.replace("https://iptv-org.github.io/epg", "https://youer-iptv.deta.dev/epg")
    content = index_header + "\n".join(lines)
    with open("new_cn.m3u8", "w", encoding="utf8") as wf:
        wf.write(content)

    deta = Deta("你的 deta project key")
    drive = deta.Drive("iptv")
    drive.put("cn.m3u8", content.encode("utf8"))


if __name__ == "__main__":
    app()