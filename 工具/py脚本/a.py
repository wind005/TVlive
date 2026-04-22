import requests
import os
import re
import sys
import base64
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

# ================= 配置区域 =================
# 1. Cookie 配置
COOKIE_FILE = "cookie.txt"                    # Cookie 文件路径

# 2. Gitee 推送配置 (填入你的信息)
GITEE_TOKEN = "cf664e045a4258ee7a1dca"        # Gitee 私人令牌
GITEE_USER = "zkkm2580"                       # Gitee 个人主页URL里的英文用户名
GITEE_REPO = "udpxy"                          # 你的仓库名称

# 3. 其他配置
TEMPLATE_DIR = "rtp"                          # 母版文件夹名称
# ============================================

# 中国省份全称及简称对照表，用于智能嗅探
PROVINCES = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", 
             "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", 
             "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西", 
             "甘肃", "青海", "宁夏", "新疆"]

def load_cookie_from_file():
    """从cookie.txt文件读取Cookie字符串"""
    if not os.path.exists(COOKIE_FILE):
        print(f"[!] 错误: 找不到cookie文件 '{COOKIE_FILE}'")
        print(f"[!] 请创建 {COOKIE_FILE} 文件并将Cookie内容写入其中")
        return None
    
    try:
        with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
            cookie_content = f.read().strip()
        
        if not cookie_content:
            print(f"[!] 错误: cookie文件 '{COOKIE_FILE}' 为空")
            return None
        
        print(f"[√] 成功从 {COOKIE_FILE} 加载Cookie")
        return cookie_content
        
    except Exception as e:
        print(f"[!] 读取cookie文件失败: {e}")
        return None

def parse_cookie(cookie_string):
    """解析Cookie字符串为字典"""
    cookies = {}
    for item in cookie_string.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies

def get_root_domain(domain):
    """提取根域名，防 DDNS 假去重"""
    if re.match(r'^\d+\.\d+\.\d+\.\d+$', domain): return domain
    parts = domain.split('.')
    if len(parts) >= 3:
        if parts[-2] in ['com', 'net', 'org', 'gov', 'edu', 'gx'] or len(parts[-2]) <= 2:
            return ".".join(parts[-3:])
        else: return ".".join(parts[-2:])
    return domain

def extract_province(filename):
    """智能识别省份"""
    for p in PROVINCES:
        if p in filename: return p
    return None

def check_url(url):
    """16KB 深度硬核测流验证 (拒绝假存活)"""
    try:
        with requests.get(url, stream=True, timeout=(3, 5)) as resp:
            if resp.status_code == 200:
                downloaded = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk: downloaded += len(chunk)
                    if downloaded >= 16384:
                        print(f"  [√ 真有效] {url}")
                        return url
    except Exception: pass
    return None

def check_and_clear_existing(txt_file, m3u_file):
    """检测当前目录文件，失效则雷霆清空"""
    if not os.path.exists(txt_file): return False
    urls = []
    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(r'https?://[^\s,]+', line)
                if match: urls.append(match.group())
                if len(urls) >= 2: break
    except Exception: return False

    if urls:
        print(f"[*] 测试现有文件 [{txt_file}] ...")
        for url in urls:
            if check_url(url):
                print(f"[!] 结论: 源依然坚挺，跳过本省份。")
                return True
    
    print(f"[*] 结论: 源已失效，正在清空旧文件...")
    for file in [txt_file, m3u_file]:
        with open(file, 'w', encoding='utf-8') as f: f.write("") 
    return False

def get_quake_assets(cookie_string, province):
    """使用 Cookie 方式请求指定省份节点"""
    url = "https://quake.360.net/api/search/query_string/quake_service"
    
    # 构建查询语句
    query_str = f'province:"{province}" AND app:"udpxy" AND is_domain=true'
    
    cookies = parse_cookie(cookie_string)
    
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Authorization': '233',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Host': 'quake.360.net',
        'Origin': 'https://quake.360.net',
        'Referer': 'https://quake.360.net/quake/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "latest": True,
        "ignore_cache": False,
        "shortcuts": [],
        "query": query_str,
        "start": 0,
        "size": 100,
        "device": {
            "device_type": "PC",
            "os": "Windows",
            "os_version": "10.0",
            "language": "zh_CN",
            "network": "4g",
            "browser_info": "Chrome（版本: 144.0.0.0&nbsp;&nbsp;内核: Blink）",
            "fingerprint": "1fc1fe47",
            "user_agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
            "date": "2025/01/01 00:00:00",
            "UUID": "97512d6f-4347-5c5a-bbfe-2aa08d67c560"
        }
    }

    print(f"[*] 正在请求 [{province}] 地区的新节点...")
    try:
        response = requests.post(url, headers=headers, cookies=cookies, json=payload, timeout=15)
        
        # 检查HTTP状态码
        if response.status_code == 401:
            print(f"[!] Cookie认证失败 (HTTP 401)")
            print(f"[!] 请更新 {COOKIE_FILE} 文件中的Cookie内容")
            return None  # 返回None表示Cookie失效
        
        if response.status_code != 200:
            print(f"[!] HTTP请求失败，状态码: {response.status_code}")
            return []
        
        result = response.json()
        
        # 检查API返回码
        if result.get('code') == 0:
            data = result.get('data', [])
            print(f"[√] 成功获取 {len(data)} 条数据")
            return data
        elif result.get('code') == 4004:
            print(f"[!] Cookie已过期或触发限速 (错误码: 4004)")
            print(f"[!] 请更新 {COOKIE_FILE} 文件中的Cookie内容")
            return None  # 返回None表示Cookie失效
        else:
            error_msg = result.get('message', '未知错误')
            print(f"[!] API返回错误: {error_msg}")
            return []
            
    except requests.exceptions.Timeout:
        print(f"[!] 请求超时")
        return []
    except Exception as e:
        print(f"[!] 网络请求失败: {e}")
        return []

def txt_to_m3u_format(txt_content):
    """智能转换 M3U 分组格式"""
    m3u_lines = []
    current_group = "未分类"
    for line in txt_content.splitlines():
        line = line.strip()
        if not line: continue
        if '#genre#' in line:
            current_group = line.split(',')[0].strip()
        elif ',' in line:
            name, url = [p.strip() for p in line.split(',', 1)]
            m3u_lines.append(f'#EXTINF:-1 group-title="{current_group}",{name}\n{url}')
    return "\n".join(m3u_lines)

def process_province(cookie_string, template_filename):
    """单一省份核心流水线"""
    province = extract_province(template_filename)
    if not province: return

    template_path = os.path.join(TEMPLATE_DIR, template_filename)
    out_txt = template_filename 
    out_m3u = template_filename.replace('.txt', '.m3u')

    # 1. 检测已有文件
    if check_and_clear_existing(out_txt, out_m3u): return

    # 2. 读取母版内容
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # 动态嗅探组播靶标 (自动识别 udp/rtp/igmp 及 IP端口)
    match = re.search(r'(?:https?://[^/,]+/)?(udp|rtp|igmp)(?:/|://)(\d+\.\d+\.\d+\.\d+:\d+)', template_content, re.IGNORECASE)
    if not match: return
    protocol, mcast_target = match.group(1).lower(), match.group(2)
    print(f"[*] 成功提取 [{province}] 测试靶标: /{protocol}/{mcast_target}")

    # 3. 获取 Quake 资产并绝对去重
    assets = get_quake_assets(cookie_string, province)
    
    # 检查Cookie是否失效
    if assets is None:
        return False  # 返回False表示Cookie失效，需要终止整个程序
    
    if not assets:
        print(f"[-] [{province}] 未获取到任何资产")
        return True  # 返回True表示继续处理

    urls_to_test, host_map, seen_root_domains = [], {}, set()
    for item in assets:
        # 提取 host（优先级: service.http.host > domain > hostname > ip）
        host = None
        try:
            if 'service' in item and 'http' in item['service'] and 'host' in item['service']['http']:
                host = item['service']['http']['host']
        except:
            pass
        
        if not host:
            host = item.get('domain') or item.get('hostname') or item.get('ip')
        
        port = item.get('port')
        if host and port:
            pure_domain = host.split(':')[0]
            root_domain = get_root_domain(pure_domain)
            if root_domain not in seen_root_domains:
                seen_root_domains.add(root_domain)
                full_host = f"{host}:{port}"
                test_url = f"http://{full_host}/{protocol}/{mcast_target}"
                urls_to_test.append(test_url)
                host_map[test_url] = full_host
    
    if not urls_to_test:
        print(f"[-] [{province}] 没有可测试的URL")
        return True
    
    print(f"[*] 开始并发测试 {len(urls_to_test)} 个新源...")

    # 4. 并发深度测流
    valid_hosts = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for res_url in executor.map(check_url, urls_to_test):
            if res_url: 
                valid_hosts.append(host_map[res_url])

    # 5. 克隆母版生成纯净文件
    if valid_hosts:
        pattern = re.compile(r'(?:https?://[^/,]+/)?(udp|rtp|igmp)(?:/|://)(\d+\.\d+\.\d+\.\d+:\d+)', re.IGNORECASE)
        with open(out_txt, 'w', encoding='utf-8') as f_txt, open(out_m3u, 'w', encoding='utf-8') as f_m3u:
            f_m3u.write("#EXTM3U\n")
            for host in valid_hosts:
                new_txt_block = pattern.sub(f'http://{host}/\\1/\\2', template_content)
                f_txt.write(new_txt_block + "\n\n")
                f_m3u.write(txt_to_m3u_format(new_txt_block) + "\n\n")
        print(f"[+] 完美！[{province}] 更新完成，获取 {len(valid_hosts)} 个纯净节点。")
    else:
        print(f"[-] [{province}] 所有节点测试失败，无一存活。")
    
    return True

def push_to_gitee(filename):
    """
    Gitee 终极同步模块（修复中文乱码与新建/更新分离机制）
    """
    if not os.path.exists(filename): return
    if not GITEE_TOKEN or GITEE_TOKEN.startswith("填入"): return 

    print(f"\n[*] 正在将 [{filename}] 同步推送至 Gitee 仓库...")
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    g_user = GITEE_USER.strip()
    g_repo = GITEE_REPO.strip()
    
    # 对中文文件名进行 URL 编码，防止被识别为请求根目录
    safe_filename = urllib.parse.quote(filename)
    api_url = f"https://gitee.com/api/v5/repos/{g_user}/{g_repo}/contents/{safe_filename}"

    sha = ""
    try:
        # 获取文件信息
        get_resp = requests.get(api_url, params={"access_token": GITEE_TOKEN}, timeout=10)
        if get_resp.status_code == 200:
            resp_data = get_resp.json()
            # 防御性验证，就算被解析成了 list 也要安全遍历提取 sha
            if isinstance(resp_data, dict):
                sha = resp_data.get("sha", "")
            elif isinstance(resp_data, list):
                for item in resp_data:
                    if item.get("name") == filename:
                        sha = item.get("sha", "")
                        break
    except Exception as e:
        print(f"[-] 获取文件状态异常: {e}")

    payload = {
        "access_token": GITEE_TOKEN,
        "content": b64_content,
        "message": f"Auto update {filename} at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    }

    try:
        if sha:
            # 有 sha 代表文件存在，必须使用 PUT 进行更新
            payload["sha"] = sha 
            put_resp = requests.put(api_url, json=payload, timeout=15)
            status_code = put_resp.status_code
            resp_text = put_resp.text
        else:
            # 没有 sha 代表这是个新文件，必须使用 POST 进行新建
            post_resp = requests.post(api_url, json=payload, timeout=15)
            status_code = post_resp.status_code
            resp_text = post_resp.text

        if status_code in [200, 201]:
            print(f"[+] 成功！[{filename}] 已送达 Gitee 仓库！")
        else:
            print(f"[-] 推送失败，Gitee 响应: {resp_text}")
    except Exception as e:
        print(f"[!] 推送请求出错: {e}")
        
    # 加入0.5秒延迟，防止密集提交触发 Gitee 并发拦截
    time.sleep(0.5)

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 加载 Cookie
    print("[*] 正在加载Cookie配置...")
    cookie_string = load_cookie_from_file()
    if not cookie_string:
        print("[!] 无法加载Cookie，程序退出")
        print(f"[!] 请确保 {COOKIE_FILE} 文件存在且包含有效的Cookie字符串")
        return
    
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
        print(f"[!] 没有找到 '{TEMPLATE_DIR}' 目录，已自动创建。请放入模板后重新运行！")
        return

    template_files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith('.txt')]
    if not template_files:
        print(f"[!] '{TEMPLATE_DIR}' 目录中空空如也，请放入各省市的模板文件。")
        return

    # 流水线处理各省份
    cookie_valid = True
    for filename in template_files:
        if not cookie_valid:
            break
            
        print(f"\n" + "="*50)
        print(f" 正在处理兵工厂任务: {filename}")
        print("="*50)
        result = process_province(cookie_string, filename)
        
        # 如果返回False，表示Cookie失效，终止所有处理
        if result is False:
            print(f"\n[!] Cookie已失效，程序终止运行！")
            print(f"[!] 请更新 {COOKIE_FILE} 文件中的Cookie内容后重新运行")
            cookie_valid = False
            break
    
    if not cookie_valid:
        return
    
    print("\n[√] 流水线本地文件生成完毕，准备执行云端同步...")

    # 遍历当前目录下生成的最新源文件，推送到 Gitee
    for file in os.listdir('.'):
        if file.endswith('.txt') or file.endswith('.m3u'):
            push_to_gitee(file)

    print("\n[√] 史诗级闭环！全网搜源 -> 深度测流 -> 覆盖生成 -> 云端发布，全部完成！")

if __name__ == '__main__':
    main()